"""Tests for the TF-IDF retrieval engine."""

from chatbot.engine import ChatbotEngine, split_into_passages, tokenize


def write_reference(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_tokenize_lowercases_and_splits():
    assert tokenize("Hello, World! 123") == ["hello", "world", "123"]


def test_split_into_passages_attaches_heading():
    text = "## Hours\n\nThe lab is open 9 to 5.\n\nAnother passage here."
    passages = split_into_passages(text)
    assert passages[0].startswith("Hours")
    assert "open 9 to 5" in passages[0]
    assert passages[1] == "Another passage here."


def test_query_returns_relevant_passage(tmp_path):
    write_reference(
        tmp_path,
        "faq.md",
        "## Hours\n\nThe lab is open Monday to Friday from 9 AM to 5 PM.\n\n"
        "## Software\n\nWe mainly use Python and R for analysis.",
    )
    engine = ChatbotEngine(tmp_path)
    answer = engine.query("When is the lab open?")
    assert answer.found is True
    assert "Monday to Friday" in answer.text
    assert answer.source == "faq.md"
    assert answer.score > 0


def test_query_picks_best_of_multiple_files(tmp_path):
    write_reference(tmp_path, "a.md", "The microscope can be booked online.")
    write_reference(tmp_path, "b.md", "Python and R are used for data analysis.")
    engine = ChatbotEngine(tmp_path)
    answer = engine.query("What tools are used for data analysis?")
    assert answer.found is True
    assert "Python" in answer.text
    assert answer.source == "b.md"


def test_query_unknown_topic_not_found(tmp_path):
    write_reference(tmp_path, "faq.md", "The lab is open from 9 to 5.")
    engine = ChatbotEngine(tmp_path)
    answer = engine.query("What is the airspeed velocity of a swallow?")
    assert answer.found is False


def test_empty_question_is_handled(tmp_path):
    write_reference(tmp_path, "faq.md", "The lab is open from 9 to 5.")
    engine = ChatbotEngine(tmp_path)
    answer = engine.query("   ")
    assert answer.found is False


def test_no_reference_documents(tmp_path):
    engine = ChatbotEngine(tmp_path)
    answer = engine.query("anything")
    assert answer.found is False
    assert engine.documents == []


def test_only_supported_extensions_indexed(tmp_path):
    write_reference(tmp_path, "good.md", "Indexed content about microscopes.")
    write_reference(tmp_path, "ignore.json", "should not be indexed")
    engine = ChatbotEngine(tmp_path)
    assert all(doc.source == "good.md" for doc in engine.documents)
