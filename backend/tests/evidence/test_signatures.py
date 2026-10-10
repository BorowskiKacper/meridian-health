import inspect

import pytest

from app.evidence import (
    search_guidelines,
    search_medical_web,
    search_payer_docs,
    web_search,
)

TEXT_ONLY = [search_medical_web, search_payer_docs, web_search]


def test_search_guidelines_takes_text_and_corpus_and_not_patient_id():
    params = list(inspect.signature(search_guidelines).parameters)
    assert params[:2] == ["text", "corpus"]
    assert "patient_id" not in params


@pytest.mark.parametrize("fn", TEXT_ONLY, ids=lambda fn: fn.__name__)
def test_text_search_takes_text_and_not_patient_id(fn):
    params = list(inspect.signature(fn).parameters)
    assert params[:1] == ["text"]
    assert "patient_id" not in params
