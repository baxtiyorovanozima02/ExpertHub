"""
RAG pipeline va Search logikasi uchun unit testlar.
Testlar: generate_answer, _build_context, find_relevant_chunks

OpenAI (LLM), Qdrant va SentenceTransformer — mock qilinadi.
"""
import pytest
from unittest.mock import patch, MagicMock, call

from app.ai.rag import generate_answer, _build_context, build_chat_history
from app.ai.search import find_relevant_chunks
from app.models.message import Message



class TestBuildContext:
    def test_returns_no_info_message_when_no_chunks(self):
        db = MagicMock()
        with patch("app.ai.rag.find_relevant_chunks", return_value=[]):
            result = _build_context(db, "Savol", category_id=None)
        assert "topilmadi" in result

    def test_returns_joined_chunks(self):
        db = MagicMock()
        chunk1 = MagicMock()
        chunk1.content = "Birinchi ma'lumot"
        chunk2 = MagicMock()
        chunk2.content = "Ikkinchi ma'lumot"
        with patch("app.ai.rag.find_relevant_chunks", return_value=[chunk1, chunk2]):
            result = _build_context(db, "Savol", category_id=1)
        assert "Birinchi ma'lumot" in result
        assert "Ikkinchi ma'lumot" in result

    def test_each_chunk_prefixed_with_dash(self):
        db = MagicMock()
        chunk = MagicMock()
        chunk.content = "Test ma'lumot"
        with patch("app.ai.rag.find_relevant_chunks", return_value=[chunk]):
            result = _build_context(db, "Savol", category_id=None)
        assert result.startswith("- ")

    def test_passes_category_id_to_search(self):
        db = MagicMock()
        with patch("app.ai.rag.find_relevant_chunks", return_value=[]) as mock_search:
            _build_context(db, "Savol", category_id=42)
        mock_search.assert_called_once_with(db, "Savol", category_id=42, top_k=5)




class TestGenerateAnswer:
    def _mock_llm_response(self, text="LLM javobi"):
        mock_response = MagicMock()
        mock_response.content = text
        return mock_response

    def test_generate_answer_returns_string(self):
        db = MagicMock()
        with patch("app.ai.rag.find_relevant_chunks", return_value=[]):
            with patch("app.ai.rag._llm") as mock_llm:
                mock_chain = MagicMock()
                mock_chain.invoke.return_value = self._mock_llm_response("Javob matni")
                mock_llm.__ror__ = MagicMock(return_value=mock_chain)
                with patch("app.ai.rag._PROMPT") as mock_prompt:
                    mock_prompt.__or__ = MagicMock(return_value=mock_chain)
                    result = generate_answer(db, "Savol nima?")
        assert isinstance(result, str)

    def test_generate_answer_uses_question(self):
        db = MagicMock()
        chunk = MagicMock()
        chunk.content = "Kontekst ma'lumoti"
        with patch("app.ai.rag.find_relevant_chunks", return_value=[chunk]):
            with patch("app.ai.rag._PROMPT") as mock_prompt:
                mock_chain = MagicMock()
                mock_chain.invoke.return_value = self._mock_llm_response("Javob")
                mock_prompt.__or__ = MagicMock(return_value=mock_chain)
                generate_answer(db, "Mening savolim")
                call_kwargs = mock_chain.invoke.call_args[0][0]
                assert call_kwargs["question"] == "Mening savolim"

    def test_generate_answer_passes_context_to_llm(self):
        db = MagicMock()
        chunk = MagicMock()
        chunk.content = "Muhim ma'lumot"
        with patch("app.ai.rag.find_relevant_chunks", return_value=[chunk]):
            with patch("app.ai.rag._PROMPT") as mock_prompt:
                mock_chain = MagicMock()
                mock_chain.invoke.return_value = self._mock_llm_response("Javob")
                mock_prompt.__or__ = MagicMock(return_value=mock_chain)
                generate_answer(db, "Savol")
                call_kwargs = mock_chain.invoke.call_args[0][0]
                assert "Muhim ma'lumot" in call_kwargs["context"]

    def test_generate_answer_with_category_id(self):
        db = MagicMock()
        with patch("app.ai.rag.find_relevant_chunks", return_value=[]) as mock_search:
            with patch("app.ai.rag._PROMPT") as mock_prompt:
                mock_chain = MagicMock()
                mock_chain.invoke.return_value = self._mock_llm_response()
                mock_prompt.__or__ = MagicMock(return_value=mock_chain)
                generate_answer(db, "Savol", category_id=5)
        mock_search.assert_called_once_with(db, "Savol", category_id=5, top_k=5)


class TestBuildChatHistory:
    def _make_message(self, role, content):
        msg = MagicMock(spec=Message)
        msg.role = role
        msg.content = content
        return msg

    def test_empty_messages_returns_empty_list(self):
        result = build_chat_history([])
        assert result == []

    def test_user_message_becomes_human_message(self):
        from langchain_core.messages import HumanMessage
        msgs = [self._make_message("user", "Salom")]
        result = build_chat_history(msgs)
        assert len(result) == 1
        assert isinstance(result[0], HumanMessage)
        assert result[0].content == "Salom"

    def test_assistant_message_becomes_ai_message(self):
        from langchain_core.messages import AIMessage
        msgs = [self._make_message("assistant", "Javob")]
        result = build_chat_history(msgs)
        assert len(result) == 1
        assert isinstance(result[0], AIMessage)
        assert result[0].content == "Javob"

    def test_mixed_messages_preserves_order(self):
        from langchain_core.messages import HumanMessage, AIMessage
        msgs = [
            self._make_message("user", "Savol 1"),
            self._make_message("assistant", "Javob 1"),
            self._make_message("user", "Savol 2"),
        ]
        result = build_chat_history(msgs)
        assert len(result) == 3
        assert isinstance(result[0], HumanMessage)
        assert isinstance(result[1], AIMessage)
        assert isinstance(result[2], HumanMessage)


class TestFindRelevantChunks:
    def test_returns_empty_list_when_no_chunk_ids(self):
        db = MagicMock()
        with patch("app.ai.search.generate_embedding", return_value=[0.1] * 384):
            with patch("app.ai.search.qdrant_client.search_similar_documents", return_value=[]):
                with patch("app.ai.search.qdrant_client.search_similar_chunks", return_value=[]):
                    result = find_relevant_chunks(db, "Savol")
        assert result == []

    def test_returns_chunks_from_db(self):
        db = MagicMock()
        from app.models.document_chunk import DocumentChunk
        fake_chunk = MagicMock(spec=DocumentChunk)
        fake_chunk.id = 1
        db.query.return_value.filter.return_value.all.return_value = [fake_chunk]
        with patch("app.ai.search.generate_embedding", return_value=[0.1] * 384):
            with patch("app.ai.search.qdrant_client.search_similar_documents", return_value=[10]):
                with patch("app.ai.search.qdrant_client.search_similar_chunks", return_value=[1]):
                    result = find_relevant_chunks(db, "Savol")
        assert len(result) == 1
        assert result[0].id == 1

    def test_fallback_when_no_chunks_but_docs_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        with patch("app.ai.search.generate_embedding", return_value=[0.1] * 384):
            with patch("app.ai.search.qdrant_client.search_similar_documents", return_value=[5]):
                with patch("app.ai.search.qdrant_client.search_similar_chunks", side_effect=[[], []]):
                    result = find_relevant_chunks(db, "Savol")
        assert result == []

    def test_passes_category_id_to_qdrant(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        with patch("app.ai.search.generate_embedding", return_value=[0.1] * 384):
            with patch("app.ai.search.qdrant_client.search_similar_documents", return_value=[]) as mock_docs:
                with patch("app.ai.search.qdrant_client.search_similar_chunks", return_value=[]):
                    find_relevant_chunks(db, "Savol", category_id=7)
        mock_docs.assert_called_once_with(
            query_vector=[0.1] * 384,
            category_id=7,
            top_k=pytest.approx(mock_docs.call_args[1].get("top_k", 3), abs=10),
        )

    def test_chunks_sorted_by_qdrant_order(self):
        db = MagicMock()
        from app.models.document_chunk import DocumentChunk
        chunk_a = MagicMock(spec=DocumentChunk)
        chunk_a.id = 2
        chunk_b = MagicMock(spec=DocumentChunk)
        chunk_b.id = 1
        db.query.return_value.filter.return_value.all.return_value = [chunk_a, chunk_b]
        with patch("app.ai.search.generate_embedding", return_value=[0.1] * 384):
            with patch("app.ai.search.qdrant_client.search_similar_documents", return_value=[10, 11]):
                with patch("app.ai.search.qdrant_client.search_similar_chunks", return_value=[1, 2]):
                    result = find_relevant_chunks(db, "Savol")
        assert result[0].id == 1
        assert result[1].id == 2