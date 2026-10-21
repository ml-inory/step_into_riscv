# 从逻辑门到 RISC-V

> 一份"自己动手从 0 搭 CPU"的学习笔记。
> 从 NAND 门开始，经过加法器、ALU、触发器、内存，最后落成一个能跑程序的**单周期 RV32I 处理器**。

主要参考教材：*Digital Design and Computer Architecture: RISC-V Edition*（DDCA，PDF 放在 `pdf/`）

![目标结构：单周期处理器](images/scp.png)

*目标结构就是 DDCA 的图 7.12，`rtl/` 下的实现以此为目标。*

---

## 这套笔记怎么组织的

同一批部件用**两种载体**各走一遍：

| 载体 | 位置 | 用来干什么 |
| --- | --- | --- |
| Logisim 电路 | `gates/*.circ` | 先"画出来、看清楚"，理解门级实现 |
| SystemVerilog RTL | `rtl/*.sv` | 再"写出来、跑起来"，用仿真验证 |

前 8 章基本是连连看，把每个部件的门级实现搞明白；第 9 章开始换 HDL，之后
Logisim 只用来做直观的逻辑验证。

## 目录结构

```
docs/     学习笔记正文（13 章）
gates/    Logisim 电路（.circ），可加载后直接运行
images/   笔记里用到的图
pdf/      DDCA 教材
rtl/      单周期 RV32I CPU 的 SystemVerilog 实现
tb/       测试程序（汇编）与迷你汇编器
sim/      仿真运行脚本
```

## 学习路线

| 章 | 主题 | 电路 | 关键点 |
| --- | --- | --- | --- |
| [00](docs/00-基础逻辑门.md) | 基础逻辑门 | [logic_gates.circ](gates/logic_gates.circ) | 用 NAND 搭出 NOT/AND/OR/XOR |
| [01](docs/01-加法电路.md) | 加法电路 | [adder.circ](gates/adder.circ) | 半加器 → 全加器 → 行波/超前进位 |
| [02](docs/02-用加法器做减法.md) | 用加法器做减法 | [sub.circ](gates/sub.circ) | 补码：减法就是加负数 |
| [03](docs/03-比较器.md) | 比较器 | [comparators.circ](gates/comparators.circ) | EQ / LT，以及有符号比较 |
| [04](docs/04-选择器.md) | 选择器 | [mux.circ](gates/mux.circ) | MUX/DEMUX，之后到处都在用 |
| [05](docs/05-ALU.md) | ALU | [alu.circ](gates/alu.circ) | 把运算 + 选择器组合起来 |
| [06](docs/06-锁存器和触发器.md) | 锁存器和触发器 | [latch_and_flip_flop.circ](gates/latch_and_flip_flop.circ) | 电路终于能"记住"东西 |
| [07](docs/07-状态机.md) | 状态机 | [tracfic_light.circ](gates/tracfic_light.circ) | Moore/Mealy，交通灯例子 |
| [08](docs/08-内存.md) | 内存 | — | SRAM/DRAM 单元、ROM、为什么要 DDR |
| [09](docs/09-HDL.md) | HDL | — | 换 SystemVerilog，Logisim 退居二线 |
| [10](docs/10-指令集架构.md) | 指令集架构 | — | RISC-V RV32I 的指令分类 |
| [11](docs/11-程序计数器.md) | 程序计数器 | [pc.circ](gates/pc.circ) | PC + 下一个 PC 的选择 |
| [12](docs/12-单周期处理器.md) | 单周期处理器 | `rtl/` | 把所有部件拼起来 |

## 最终成果

一个**单周期** RV32I 子集 CPU（`rtl/cpu.sv`），一条指令一个时钟周期。

**已支持的 10 条指令**：

| 类型 | 指令 |
| --- | --- |
| 算术 | `ADD` `ADDI` |
| 立即数 | `LUI` |
| 访存 | `LW` `SW` |
| 条件分支 | `BNE` `BLT` `BGE`（`BLT`/`BGE` 为**有符号**比较） |
| 跳转 | `JAL` `JALR` |

**模块划分**：

| 模块 | 作用 | 备注 |
| --- | --- | --- |
| `pc.sv` | 程序计数器 | 时序：每拍更新为 `pc+4` 或跳转目标 |
| `instr_mem.sv` | 指令 ROM，4 KiB | **组合读**，字节地址、小端 |
| `reg_file.sv` | 32×32 寄存器堆，2 读 1 写 | **组合读**，写口时序；`x0` 硬连 0 |
| `alu.sv` | 运算 + 三个条件标志 | 组合；`neq`/`lt`/`ge` 供分支使用 |
| `ctrl_unit.sv` | 主控制单元 | 组合译码，`ResultSrc` 2 位、`ImmSrc` 3 位 |
| `data_mem.sv` | 数据 RAM，256×32（1 KiB） | **组合读**，写口时序；字地址 `A[9:2]` |

**数据通路的几条关键约定**：

- 所有"部件读"都是组合的 —— 单周期里指令、寄存器、内存必须在同一拍拿到；
  只有 PC、寄存器写、内存写是时序的。
- 立即数有 5 种格式（I/S/B/J/U），`ImmExt` 由 `ImmSrc` 选择，拼接宽度必须
  正好 32 位。
- 写回三选一：`ALUResult` / 内存读数据 / `pc+4`（给 `JAL`/`JALR` 存链接）。
- `JALR` 的目标是 `(rs1 + imm) & ~1`，不是 `pc + imm`。

## 跑起来

**依赖**：Icarus Verilog（用 `-g2012` 语义）+ Python 3.8+。

```bash
# 跑完整回归程序（覆盖上面 10 条指令）
python sim/run_tb.py

# 跑一个专门的求和程序：1 + 2 + ... + 10
python sim/run_tb.py --program sum

# 所有程序一起跑
python sim/run_tb.py --all

# 打印每拍的 pc / 指令，调试用
python sim/run_tb.py --trace

# 检验 testbench 本身够不够灵敏（往 RTL 里注入 8 种 bug，看能不能抓到）
python sim/mutation_test.py
```

产物都落在 `sim/build/`：`instr_mem.hex`（机器码）、`expected.hex`（期望寄存器
状态）、`program.lst`（反汇编清单）。

### 关于 `sim/ivl.py`

`iverilog.exe` 内部通过 `system()` 调用 `ivlpp` / `ivl`，在某些 Windows 环境里
（`cmd.exe` 不可用时）它会**静默退出、不报任何错**。`sim/ivl.py` 直接调
CreateProcess 复刻了驱动流程（预处理 → 展开 → `vvp`），绕开 shell，所以能跑。
正常环境下直接用 `iverilog` / `vvp` 也没问题。

## 测试程序怎么写

测试程序就是普通的汇编源码（`tb/*.S`），用 `tb/asm.py` 汇编。**期望值写在程序
里**：

```asm
// 计算 1 + 2 + ... + 10
_start:
        addi    x1, x0, 0           // sum = 0
        addi    x2, x0, 1           // i   = 1
        addi    x3, x0, 10          // n   = 10
loop:
        add     x1, x1, x2          // sum += i
        addi    x2, x2, 1           // i++
        bge     x3, x2, loop        // 10 >= i ? 继续
done:
        jal     x0, done            // 原地停机

// expect x1 = 55        ; 1+2+...+10
// expect x2 = 11        ; 循环变量自增到 11 后退出
// expect x3 = 10
```

`// expect xN = 值` 会被汇编器收进 `expected.hex`，testbench 拿它对整个寄存器堆
逐项比对（没写的寄存器一律要求为 0）。所以**同一个 testbench 能跑任意程序**，
加新测试不用改 TB。


## 参考

- **DDCA: Digital Design and Computer Architecture, RISC-V Edition**（Harris & Harris）
  —— 主线参考书，PDF 在 `pdf/`；[作者配套站点](https://pages.hmc.edu/harris/ddca/)有各版课件和习题
- [logisim.app](https://logisim.app/) —— 本仓库 `.circ` 都是用它画的
- [HDLBits](https://hdlbits.01xz.net/wiki/Main_Page) —— 练 SystemVerilog
- [nand2tetris](https://www.nand2tetris.org/course) —— 讲清了"从 NAND 开始能走多远"
- [RISC-V 指令集手册](https://riscv.org/technical/specifications/)

## License

[MIT](LICENSE) © 祈Inory
