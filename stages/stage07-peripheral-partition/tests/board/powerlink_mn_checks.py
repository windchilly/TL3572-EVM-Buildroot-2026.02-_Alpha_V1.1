"""Pure GsOff lifecycle result checks; no board IO at import."""
from powerlink_eth_checks import fields, quiescent
def passive_owner(state):
    expected = dict(ready='1', pending='0', running='0', seq='1', done='1', state='0', nmt='0x0',
        processes='128', events='0', cmd='6', rc='0x0', runtime='0x0')
    return all(state.get(key) == value for key, value in expected.items())

def validate_lifecycle(reply):
    result = fields(reply, 'PLK UP2 MN')
    expected = dict(rc='0', clean='1', stage='5', stack='0x0', loops='128', state='0', nmt='0x0',
        rx='0', tx='0', txdesc='0', rxerr='0', txerr='0', fatal='0', irqs='0', callbacks='0', timer='0/0')
    if any(result.get(key) != value for key, value in expected.items()) or not quiescent(result):
        raise ValueError('full-stack GsOff lifecycle failed or resources not proven stopped')
    if int(result['mac'], 0) & 0x0030e003 != 0xc003: raise ValueError('MAC not enabled100-half during prepare')
    return result
