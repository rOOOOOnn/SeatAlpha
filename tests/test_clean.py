from pipeline.clean import canonical_broker, classify_behavior, symbol_from_contract


def test_broker_normalization():
    assert canonical_broker("中信期货有限公司") == "中信期货"
    assert canonical_broker("永安期货（代客）") == "永安期货"


def test_contract_symbol():
    assert symbol_from_contract("rb2609") == "RB"


def test_behavior():
    assert classify_behavior(10, -2) == "强加多"
    assert classify_behavior(-10, 2) == "强加空"
