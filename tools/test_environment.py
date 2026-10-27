"""Generic tooling checks only; no shear-wall model or code provisions."""

import io

import pytest


def test_opensees_elastic_cantilever():
    """Compare an arbitrary-unit elastic beam with P L^3 / (3 E I)."""
    import openseespy.opensees as ops

    ops.wipe()
    try:
        length, modulus, inertia, area, load = 3.0, 200e9, 8e-6, 0.01, 1000.0
        ops.model("basic", "-ndm", 2, "-ndf", 3)
        ops.node(1, 0.0, 0.0)
        ops.node(2, length, 0.0)
        ops.fix(1, 1, 1, 1)
        ops.geomTransf("Linear", 1)
        ops.element("elasticBeamColumn", 1, 1, 2, area, modulus, inertia, 1)
        ops.timeSeries("Linear", 1)
        ops.pattern("Plain", 1, 1)
        ops.load(2, 0.0, -load, 0.0)
        ops.constraints("Plain")
        ops.numberer("Plain")
        ops.system("BandGeneral")
        ops.test("NormDispIncr", 1e-12, 10)
        ops.algorithm("Linear")
        ops.integrator("LoadControl", 1.0)
        ops.analysis("Static")
        assert ops.analyze(1) == 0
        expected = -load * length**3 / (3 * modulus * inertia)
        assert ops.nodeDisp(2, 2) == pytest.approx(expected, rel=1e-10)
        ops.reactions()
        assert ops.nodeReaction(1, 2) == pytest.approx(load, rel=1e-10)
        print(f"OpenSees {ops.version()}: displacement={ops.nodeDisp(2, 2):.12g}; expected={expected:.12g}")
    finally:
        ops.wipe()


def test_numerics_and_table_roundtrip():
    import numpy as np
    import pandas as pd
    from scipy.linalg import solve

    matrix = np.array([[2.0, 1.0], [1.0, 3.0]])
    loads = np.array([5.0, 7.0])
    result = solve(matrix, loads)
    np.testing.assert_allclose(matrix @ result, loads)
    table = pd.DataFrame({"index": [1, 2], "value": result})
    restored = pd.read_csv(io.StringIO(table.to_csv(index=False)))
    np.testing.assert_allclose(restored["value"], result)


def test_headless_plot(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    fig, ax = plt.subplots()
    try:
        ax.plot([0, 1, 2], [0, 1, 4])
        output = io.BytesIO()
        fig.savefig(output, format="png")
        assert output.getvalue().startswith(b"\x89PNG\r\n\x1a\n")
        assert len(output.getvalue()) > 1000
    finally:
        plt.close(fig)


def test_streamlit_widget_execution():
    from streamlit.testing.v1 import AppTest

    page = AppTest.from_string(
        'import streamlit as st\n'
        'value = st.number_input("Generic input", value=2)\n'
        'st.metric("Generic output", value * 2)\n'
    ).run(timeout=30)
    assert not page.exception
    assert page.metric[0].value == "4"
    page.number_input[0].set_value(3).run(timeout=30)
    assert not page.exception
    assert page.metric[0].value == "6"
