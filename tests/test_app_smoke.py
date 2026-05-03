from pathlib import Path


def test_streamlit_app_exists_and_imports_analysis_flow():
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert "streamlit" in app_source
    assert "compute_peer_stats" in app_source
    assert "peer_stats_to_dataframe" in app_source


def test_streamlit_app_exposes_expected_readthrough_graph_section():
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert "Expected Read-Through" in app_source
    assert "selected_drivers_from_names" in app_source
    assert "build_expected_readthrough" in app_source
    assert "readthrough_to_dataframe" in app_source


def test_streamlit_app_labels_bloomberg_setup_errors():
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert "Bloomberg data unavailable" in app_source


def test_streamlit_app_has_dark_terminal_css():
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert "#0d1117" in app_source
    assert "#161b22" in app_source
    assert "#2dd4bf" in app_source


def test_streamlit_app_has_custom_badge_helpers():
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert "_badge" in app_source
    assert "direction-pos" in app_source
    assert "direction-neg" in app_source
    assert "magnitude-high" in app_source
    assert "confidence-low" in app_source


def test_streamlit_app_uses_loading_status():
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert "st.status" in app_source
    assert "Running analysis" in app_source


def test_streamlit_app_escapes_html_in_badges():
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert "html.escape" in app_source


def test_streamlit_app_has_caveat_without_side_stripe():
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert "border-left" not in app_source
    assert "background-color: rgba(210, 153, 34, 0.08)" in app_source


def test_streamlit_app_has_miss_driver_label():
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert '"Miss Drivers"' in app_source


def test_streamlit_app_renders_readthrough_visualizations():
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert "readthrough_visualization_dataframe" in app_source
    assert "readthrough_matrix_dataframe" in app_source
    assert "Impact Ranking" in app_source
    assert "Read-Through Matrix" in app_source
    assert "st.altair_chart" in app_source
