from importlib.metadata import version

def test_pinned_versions():
    assert version("deepagents") == "0.7.32"
    assert version("langchain") == "1.4.7"
    assert version("langchain-core") == "1.7.0"
    assert version("langgraph") == "1.2.17"

def test_package_imports():
    import agora
    assert agora.__version__ == "0.1.0"
