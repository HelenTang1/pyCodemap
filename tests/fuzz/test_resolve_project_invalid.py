import tempfile
from pathlib import Path
import pytest
import keyword

from hypothesis import given, settings, strategies as st

from pycodemap import resolve_project, ResolverConfig


@st.composite
def module_with_keyword_function(draw):
    """
    產生一個「一定非法」的 module：
    def <keyword>():
        pass
    """
    kw = draw(st.sampled_from(keyword.kwlist))  # 隨機挑一個關鍵字當名字
    src = f"def {kw}():\n    pass\n"
    return src, kw

@given(data=module_with_keyword_function())
@settings(max_examples=30, deadline=None)
def test_resolver_raises_syntaxerror_on_keyword_function(data):
    src, kw = data

    # 建一個臨時專案目錄
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        pkg = root / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "mod.py").write_text(src, encoding="utf-8")

        # Property: 對於這種「拿 keyword 當名字」的非法程式，
        # 我們期望 resolve_project 會丟出 SyntaxError（或你定義的錯誤）
        with pytest.raises(SyntaxError):
            resolve_project(root, ResolverConfig())
