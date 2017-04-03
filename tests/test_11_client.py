import json

from oic.utils.http_util import Created

from fedoidc.bundle import JWKSBundle

from fedoidc.client import Client

from fedoidc.entity import FederationEntity
from fedoidc.provider import Provider
from fedoidc import test_utils

from oic import rndstr
from oic.utils.keyio import build_keyjar

KEYDEFS = [
    {"type": "RSA", "key": '', "use": ["sig"]},
    {"type": "EC", "crv": "P-256", "use": ["sig"]}
]

SYMKEY = rndstr(16)

TOOL_ISS = 'https://localhost'

FO = {'swamid': 'https://swamid.sunet.se', 'feide': 'https://www.feide.no'}

OA = {'sunet': 'https://sunet.se', 'uninett': 'https://uninett.no'}

IA = {}

EO = {'sunet.op': 'https://sunet.se/op',
      'foodle.rp': 'https://foodle.uninett.no'}

BASE = {'sunet.op': EO['sunet.op']}

SMS_DEF = {
    OA['sunet']: {
        "discovery": {
            FO['swamid']: [
                {'request': {}, 'requester': OA['sunet'],
                 'signer_add': {'federation_usage': 'discovery'},
                 'signer': FO['swamid']},
            ],
            FO['feide']: [
                {'request': {}, 'requester': OA['sunet'],
                 'signer_add': {'federation_usage': 'discovery'},
                 'signer': FO['feide']},
            ]
        },
        "registration": {
            FO['swamid']: [
                {'request': {}, 'requester': OA['sunet'],
                 'signer_add': {'federation_usage': 'registration'},
                 'signer': FO['swamid']},
            ],
            FO['feide']: [
                {'request': {}, 'requester': OA['sunet'],
                 'signer_add': {'federation_usage': 'registration'},
                 'signer': FO['feide']},
            ]
        },
    },
    OA['uninett']: {
        "registration": {
            FO['feide']: [
                {'request': {}, 'requester': OA['uninett'],
                 'signer_add': {'federation_usage': 'registration'},
                 'signer': FO['feide']},
            ]
        }
    },
    EO['sunet.op']: {
        "response": {
            FO['swamid']: [
                {'request': {}, 'requester': OA['sunet'],
                 'signer_add': {'federation_usage': 'response'},
                 'signer': FO['swamid']},
                {'request': {}, 'requester': EO['sunet.op'],
                 'signer_add': {}, 'signer': OA['sunet']}
            ],
            FO['feide']: [
                {'request': {}, 'requester': OA['sunet'],
                 'signer_add': {'federation_usage': "response"},
                 'signer': FO['feide']},
                {'request': {}, 'requester': EO['sunet.op'],
                 'signer_add': {}, 'signer': OA['sunet']}
            ]
        }
    }
}
liss = list(FO.values())
liss.extend(list(OA.values()))
liss.extend(list(EO.values()))

signer, keybundle = test_utils.setup(KEYDEFS, TOOL_ISS, liss, SMS_DEF, OA,
                                     'ms_dir')

fo_keybundle = JWKSBundle('https://example.com')
for iss in FO.values():
    fo_keybundle[iss] = keybundle[iss]


def test_parse_pi():
    # Sunet OP
    sunet_op = 'https://sunet.se/op'

    # _kj = build_keyjar(KEYDEFS)[1]
    _kj = signer[EO['sunet.op']].signing_service.signing_keys
    op_fed_ent = FederationEntity(None, keyjar=_kj, iss=sunet_op,
                                  signer=signer['https://sunet.se'],
                                  fo_bundle=fo_keybundle)

    op = Provider(sunet_op, None, {},
                  None, {}, None, client_authn=None, symkey=SYMKEY,
                  federation_entity=op_fed_ent,
                  response_metadata_statements=signer[
                      EO['sunet.op']].metadata_statements['response'])
    op.baseurl = op.name

    # UNINETT RP
    uninett_op = 'https://foodle.uninett.no'

    _kj = build_keyjar(KEYDEFS)[1]
    rp_fed_ent = FederationEntity(None, keyjar=_kj, iss=uninett_op,
                                  signer=signer['https://uninett.no'],
                                  fo_bundle=fo_keybundle)

    rp = Client(federation_entity=rp_fed_ent, fo_priority=list(FO.values()))

    pi = op.create_fed_providerinfo()

    assert pi

    rp.parse_federation_provider_info(pi, sunet_op)

    assert len(rp.provider_federations) == 2
    assert set([r.iss for r in rp.provider_federations]) == {
        'https://swamid.sunet.se', 'https://www.feide.no'}

    # Got two alternative FOs one I can use the other I can't
    req = rp.federated_client_registration_request(
        redirect_uris='https://foodle.uninett.no/authz',
        claims=['openid', 'email', 'phone']
    )

    assert req

    resp = op.registration_endpoint(req.to_dict())

    assert isinstance(resp, Created)

    rp.parse_federation_registration(json.loads(resp.message), sunet_op)
    assert rp.federation == FO['feide']
    assert rp.registration_response
