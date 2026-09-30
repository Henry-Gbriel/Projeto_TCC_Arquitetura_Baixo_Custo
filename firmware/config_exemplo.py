# Copie para config.py (não versionado) e ajuste para cada ESP32.
WIFI_SSID = "minha-rede"
WIFI_SENHA = "minha-senha"

MQTT_HOST = "192.168.0.10"   # IP do computador que roda o Mosquitto
MQTT_PORTA = 1884            # porta do host definida no docker-compose (.env MQTT_PORTA)
MQTT_USUARIO = None
MQTT_SENHA = None
PREFIXO = "tcc"

NO_ID = "esp32-01"           # esp32-01, esp32-02 ou esp32-03

# OLED SSD1306 0,96" I2C (pinos padrão do ESP32 DevKit)
I2C_SDA = 21
I2C_SCL = 22
OLED_ENDERECO = 0x3C
OLED_LARGURA = 128
OLED_ALTURA = 64

BATIMENTO_S = 10             # intervalo de publicação do estado
