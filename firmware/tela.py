# Visualização local no OLED SSD1306 (128x64, 8 linhas de 16 caracteres).
# Se o display não responder, o nó continua funcionando e só registra no console.


class Tela:
    def __init__(self, config):
        self.oled = None
        self.no = config.NO_ID.replace("esp32-", "")
        self.mqtt_ok = False
        self.lote = "---"
        self.pos = 0
        self.total = 0
        self.erros = 0
        self.estado = "iniciando"
        try:
            from machine import I2C, Pin
            import ssd1306
            i2c = I2C(0, sda=Pin(config.I2C_SDA), scl=Pin(config.I2C_SCL), freq=400000)
            self.oled = ssd1306.SSD1306_I2C(config.OLED_LARGURA, config.OLED_ALTURA, i2c,
                                            addr=config.OLED_ENDERECO)
        except Exception as e:
            print("OLED indisponivel:", e)

    def novo_lote(self, lote_id, total):
        # "exec-000001-lote-0014" -> "014"
        numero = lote_id.split("-")[-1]
        self.lote = numero[-3:] if len(numero) >= 3 else numero
        self.total = total
        self.pos = 0
        self.erros = 0

    def mostrar(self, estado=None):
        if estado:
            self.estado = estado
        linhas = (
            "NO {}  MQTT {}".format(self.no, "OK" if self.mqtt_ok else "--"),
            "LOTE {}".format(self.lote),
            "REG  {:02d}/{:02d}".format(self.pos, self.total),
            "ERROS {:02d}".format(self.erros),
            "",
            self.estado[:16],
        )
        if self.oled is None:
            return
        try:
            self.oled.fill(0)
            for i, texto in enumerate(linhas):
                self.oled.text(texto, 0, i * 10)
            self.oled.show()
        except Exception as e:
            print("Falha OLED:", e)
