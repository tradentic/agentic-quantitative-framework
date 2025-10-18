from flows.ingest_sec_form4 import _build_arg_parser, _parse_args


def test_help_shows_symbol_default_nvda():
    parser = _build_arg_parser()
    help_text = parser.format_help()
    assert "default: NVDA" in help_text


def test_parse_args_defaults_to_nvda_symbol():
    args = _parse_args([])
    assert args.symbol == "NVDA"
