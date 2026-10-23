"""Pure parsing/acceptance checks. No board, MMIO, commands or IO at import."""


def fields(reply, prefix):
    if not reply.startswith(prefix + ' '): raise ValueError('unexpected diagnostic reply')
    result = {}
    for item in reply[len(prefix) + 1:].split():
        if item.count('=') != 1: raise ValueError('malformed diagnostic field')
        key, value = item.split('=')
        if not key or not value or key in result: raise ValueError('empty/duplicate diagnostic field')
        result[key] = value
    return result


def numbers(value, count):
    parts = value.split('/')
    if len(parts) != count: raise ValueError('wrong readback count')
    return [int(x, 0) for x in parts]


def quiescent(result):
    """A failure result may still be safely stopped; do not confuse with PASS."""
    try:
        mac, tx, rx, dma, mac_irq, dma_irq = numbers(result['stop'], 6)
        return result['clean'] == '1' and result['lease'] == '0/0' and not (
            mac & 3 or tx & 1 or rx & 1 or dma & 1 or mac_irq or dma_irq)
    except (KeyError, ValueError): return False


def validate_probe(reply):
    result = fields(reply, 'PLK UP2 ETH')
    if result.get('rc') != '0' or not quiescent(result): raise ValueError('probe failed or stop unproved')
    if numbers(result['phy'], 2) != [0x7b74, 0x4412]: raise ValueError('wrong PHY')
    if int(result['bmcr'], 0) & 0xffc0 != 0x2000: raise ValueError('PHY is not forced100-half/ANoff')
    if int(result['bmsr'], 0) & 0x2004 != 0x2004: raise ValueError('PHY lacks 100-half capability/link')
    if int(result['mac'], 0) & 0x0030e003 != 0xc000: raise ValueError('MAC is not disabled100-half')
    if int(result['tx'], 0) & 1 or int(result['rx'], 0) & 1 or int(result['dma'], 0) & 1:
        raise ValueError('DMA enabled or reset pending')
    if any(numbers(result['irq'], 2)): raise ValueError('MAC/DMA IRQ enabled')
    return result


def link_mode(text):
    values = {}
    for line in text.splitlines():
        if ':' in line:
            key, value = line.strip().split(':', 1); values[key] = value.strip()
    return {key: values.get(key) for key in ('Speed', 'Duplex', 'Auto-negotiation', 'Link detected')}
