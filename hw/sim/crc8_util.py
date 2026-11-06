"""
CRC-8 CCITT (Polynomial 0x07, Init 0x00) Utility for WindEdgeChip UART Framing
"""

def crc8(data: bytes, init: int = 0x00, poly: int = 0x07) -> int:
    crc = init
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ poly) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc

if __name__ == "__main__":
    # Test vector
    sample_data = bytes([1, 2, 255, 0, 3, 254, 1, 0, 255, 2, 1, 0, 255, 1, 0, 2])
    c = crc8(sample_data)
    print(f"CRC8 of sample: 0x{c:02X} ({c})")

