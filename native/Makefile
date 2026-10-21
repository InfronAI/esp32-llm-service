MPY_DIR = ../third_party/micropython
MOD = tinyllm_native
SRC = module.c transformer.c
ARCH = xtensawin
LINK_RUNTIME = 1
CFLAGS_EXTRA = -O3 -ffp-contract=off -fno-math-errno
include $(MPY_DIR)/py/dynruntime.mk
