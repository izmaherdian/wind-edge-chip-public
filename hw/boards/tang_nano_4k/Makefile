# Makefile Sintesis, Place & Route, dan Bitstream untuk Sipeed Tang Nano 4K (GW1NSR-LV4C)
# Toolchain open-source: OSS CAD Suite (yosys, nextpnr, gowin_pack, openFPGALoader).
#   source ~/tools/oss-cad-suite/environment && make flash-sram
TOP_MODULE = top_soc
DEVICE     = GW1NSR-LV4CQN48PC7/I6
FAMILY     = GW1NS-4
CST        = tang_nano_4k.cst
RTL_DIR    = ../../rtl
BUILD_DIR  = ../../build/tang_nano_4k
ML_DIR     = ../../../ml

RTL_SRCS   = $(RTL_DIR)/weights_rom.v \
             $(RTL_DIR)/mac4_engine.v \
             $(RTL_DIR)/post_process.v \
             $(RTL_DIR)/fsm_controller.v \
             $(RTL_DIR)/top.v \
             $(RTL_DIR)/uart_rx.v \
             $(RTL_DIR)/uart_tx.v \
             $(RTL_DIR)/top_soc.v

# nextpnr-gowin sudah diganti nextpnr-himbaechel di OSS CAD Suite baru; pakai yang tersedia.
NEXTPNR_GOWIN := $(shell command -v nextpnr-gowin 2>/dev/null)

.PHONY: all hex synth pnr pack flash flash-sram clean

all: pack

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

# Bobot ditanam di bitstream ($readmemh saat sintesis): selalu tulis ulang hex dari golden model
# (ml/golden_model.py memuat ml/forecast/model/mlp_int8.json bila ada).
hex:
	python3 -c "import sys; sys.path.insert(0, '$(ML_DIR)'); from golden_model import GoldenModelINT8 as G; \
g = G(); print('[hex] bobot', 'hasil training' if g.trained else 'ACAK (mlp_int8.json tidak ada)'); \
g.export_hex('$(RTL_DIR)/weights.hex', '$(RTL_DIR)/bias.hex')"

# Tang Nano 4K (GW1NSR-LV4C):
# -nolutram : Mencegah inferensi Shadow RAM yang tidak kompatibel
# -nowidelut : Mencegah ledakan MUX2_LUT5..8, menjaga utilisasi SLICE tetap rendah
synth: hex $(BUILD_DIR)
	cd $(RTL_DIR) && yosys -q -l ../build/tang_nano_4k/synth.log -p "read_verilog weights_rom.v mac4_engine.v post_process.v fsm_controller.v top.v uart_rx.v uart_tx.v top_soc.v; synth_gowin -nolutram -nowidelut -top $(TOP_MODULE) -json ../build/tang_nano_4k/$(TOP_MODULE)_synth.json"

pnr: synth
ifdef NEXTPNR_GOWIN
	nextpnr-gowin --json $(BUILD_DIR)/$(TOP_MODULE)_synth.json \
	              --write $(BUILD_DIR)/$(TOP_MODULE)_pnr.json \
	              --device $(DEVICE) \
	              --family $(FAMILY) \
	              --cst $(CST)
else
	nextpnr-himbaechel --json $(BUILD_DIR)/$(TOP_MODULE)_synth.json \
	                   --write $(BUILD_DIR)/$(TOP_MODULE)_pnr.json \
	                   --device $(DEVICE) \
	                   --vopt family=$(FAMILY) \
	                   --vopt cst=$(CST) \
	                   --freq 27 -l $(BUILD_DIR)/pnr.log
endif

pack: pnr
	gowin_pack -d $(FAMILY) -o $(BUILD_DIR)/wind_edge_chip.fs $(BUILD_DIR)/$(TOP_MODULE)_pnr.json

flash: pack
	openFPGALoader -b tangnano4k -f $(BUILD_DIR)/wind_edge_chip.fs

flash-sram: pack
	openFPGALoader -b tangnano4k $(BUILD_DIR)/wind_edge_chip.fs

clean:
	rm -rf $(BUILD_DIR)
