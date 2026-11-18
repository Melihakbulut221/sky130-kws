`default_nettype none
module tt_um_kws_vec8(
    input wire [7:0] ui_in, input wire [7:0] uio_in,
    output wire [7:0] uo_out, output wire [7:0] uio_out, output wire [7:0] uio_oe,
    input wire ena, input wire clk, input wire rst_n
);
    wire [2:0] opcode = uio_in[7:5];
    wire [1:0] byte_index = uio_in[4:3];
    wire [2:0] lane_index = uio_in[2:0];
    wire launch = opcode == 3'd3 || opcode == 3'd4;
    reg pending;
    always @(posedge clk) begin
        if (!rst_n) pending <= 0;
        else if (ena) pending <= launch;
    end

    wire [31:0] result [0:7];
    genvar i;
    generate for (i=0; i<8; i=i+1) begin : lane
        reg signed [7:0] weight, activation;
        wire signed [7:0] operand = opcode == 3'd3 ? $signed(ui_in) : activation;
        reg signed [15:0] product;
        reg [31:0] accumulator;
        assign result[i] = accumulator;
        always @(posedge clk) begin
            if (!rst_n) begin
                weight <= 0;
                activation <= 0;
                accumulator <= 0;
                product <= 0;
            end else if (ena) begin
                if (opcode == 1 && lane_index == i) weight <= ui_in;
                if (opcode == 2 && lane_index == i) activation <= ui_in;
                if (launch) product <= weight * operand;
                if (opcode == 5) accumulator <= 0;
                else if (pending) accumulator <= accumulator + {{16{product[15]}},product};
            end
        end
    end endgenerate
    wire [31:0] selected = result[lane_index];
    assign uo_out = selected[byte_index*8 +: 8];
    assign uio_oe = 8'h00;
    assign uio_out = 8'h00;
endmodule
`default_nettype wire
