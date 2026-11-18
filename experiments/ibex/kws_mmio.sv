// Simulation peripheral for the Ibex Simple System pointwise benchmark.
module kws_mmio (
  input logic clk_i, rst_ni, req_i, we_i,
  input logic [3:0] be_i,
  input logic [11:0] addr_i,
  input logic [31:0] wdata_i,
  output logic rvalid_o, err_o,
  output logic [31:0] rdata_o
);
  logic [7:0] cmd, pin_result;
  logic [63:0] weights [64];
  logic signed [31:0] acc [8];
  logic [31:0] packed_input, launches;
  logic [2:0] remaining;
  logic [5:0] tap;
  wire access_ok = addr_i[1:0] == 0 && be_i == 4'hf;
  wire pin_access = req_i && access_ok && addr_i < 'h400;
  assign cmd = pin_access ? addr_i[9:2] : 0;
  wire pin_launch = pin_access && we_i && cmd[7:5] == 3;

  tt_um_kws_vec8 v1 (
    .clk(clk_i), .rst_n(rst_ni), .ena(1'b1), .uio_in(cmd),
    .ui_in(wdata_i[7:0]), .uo_out(pin_result), .uio_out(), .uio_oe()
  );

  always_ff @(posedge clk_i) begin
    rvalid_o <= req_i;
    err_o <= 0;
    if (!rst_ni) begin
      rvalid_o <= 0;
      remaining <= 0;
      packed_input <= 0;
      launches <= 0;
      tap <= 0;
      rdata_o <= 0;
      for (int i = 0; i < 8; i++) acc[i] <= 0;
    end else begin
      if (remaining != 0) begin
        for (int i = 0; i < 8; i++)
          acc[i] <= acc[i] + $signed(weights[tap][8*i+:8]) * $signed(packed_input[7:0]);
        packed_input <= packed_input >> 8;
        remaining <= remaining - 1'b1;
        tap <= tap + 1'b1;
      end
      if (pin_launch || remaining != 0) launches <= launches + 1'b1;
      if (req_i) begin
        if (!access_ok) err_o <= 1;
        else if (pin_access) rdata_o <= {24'b0, pin_result};
        else if (we_i && addr_i >= 'h400 && addr_i < 'h600 && remaining == 0)
          weights[addr_i[8:3]][32*addr_i[2]+:32] <= wdata_i;
        else if (we_i && addr_i == 'h600 && remaining == 0) begin
          packed_input <= wdata_i;
          remaining <= 4;
        end else if (we_i && addr_i == 'h604 && remaining == 0) begin
          tap <= 0;
          for (int i = 0; i < 8; i++) acc[i] <= 0;
        end else if (!we_i && addr_i == 'h608) rdata_o <= {29'b0, remaining};
        else if (!we_i && addr_i == 'h60c) rdata_o <= launches;
        else if (!we_i && addr_i >= 'h620 && addr_i < 'h640 && remaining == 0)
          rdata_o <= acc[addr_i[4:2]];
        else err_o <= 1;
      end
    end
  end
endmodule
