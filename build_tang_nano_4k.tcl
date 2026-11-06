set_device GW1NSR-LV4CQN48PC7/I6
set_option -top_module top_soc
set_option -output_base_name wind_edge_chip

add_file -type verilog "hw/rtl/weights_rom.v"
add_file -type verilog "hw/rtl/mac4_engine.v"
add_file -type verilog "hw/rtl/post_process.v"
add_file -type verilog "hw/rtl/fsm_controller.v"
add_file -type verilog "hw/rtl/top.v"
add_file -type verilog "hw/rtl/uart_rx.v"
add_file -type verilog "hw/rtl/uart_tx.v"
add_file -type verilog "hw/rtl/top_soc.v"
add_file -type cst "hw/boards/tang_nano_4k/tang_nano_4k.cst"

run all

