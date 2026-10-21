`timescale 1ns/1ps
// toolchain smoke test: does the driver + vvp work at all?
module smoke;
  logic clk = 0;
  logic [7:0] cnt = 8'd0;
  logic [31:0] mem [0:7];

  always #5 clk = ~clk;

  always_ff @(posedge clk) cnt <= cnt + 8'd1;

  initial begin
    mem[0] = 32'hdead_beef;
    $display("clk toggles, cnt starts at %0d, mem[0]=%h", cnt, mem[0]);
  end

  initial begin
    repeat (4) @(posedge clk);
    #1;  // let non-blocking updates settle before sampling
    if (cnt !== 8'd4) begin
      $display("FAIL: cnt=%0d expected 4", cnt);
      $fatal(1);
    end
    $display("PASS: smoke ok, cnt=%0d", cnt);
    $finish;
  end
endmodule
