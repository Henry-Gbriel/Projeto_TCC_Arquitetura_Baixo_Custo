# Executado antes de main.py. Mantido mínimo: libera memória e desliga o log do Wi-Fi.
import gc
import esp

esp.osdebug(None)
gc.collect()
