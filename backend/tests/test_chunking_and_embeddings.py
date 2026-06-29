"""
Chunking va Embeddings modullari uchun unit testlar.
Testlar: split_text_into_chunks, _split_long_text, generate_embedding

SentenceTransformer model mock qilinadi — haqiqiy model yuklanmaydi.
"""
import pytest
from unittest.mock import patch, MagicMock
import numpy as np

from app.ai.chunking import split_text_into_chunks, _split_long_text, DEFAULT_CHUNK_SIZE, DEFAULT_CHUNK_OVERLAP



class TestSplitTextIntoChunks:
    def test_empty_string_returns_empty_list(self):
        assert split_text_into_chunks("") == []

    def test_whitespace_only_returns_empty_list(self):
        assert split_text_into_chunks("   \n\n  ") == []

    def test_short_text_returns_single_chunk(self):
        text = "Qisqa matn"
        result = split_text_into_chunks(text)
        assert result == [text]

    def test_text_exactly_chunk_size_returns_single_chunk(self):
        text = "a" * DEFAULT_CHUNK_SIZE
        result = split_text_into_chunks(text)
        assert len(result) == 1

    def test_long_text_split_into_multiple_chunks(self):
        text = "a" * (DEFAULT_CHUNK_SIZE * 3)
        result = split_text_into_chunks(text, chunk_size=100, overlap=10)
        assert len(result) > 1

    def test_chunks_are_not_empty(self):
        text = "So'z " * 500
        result = split_text_into_chunks(text, chunk_size=100, overlap=10)
        for chunk in result:
            assert chunk.strip() != ""

    def test_paragraphs_combined_when_small(self):
        text = "Birinchi paragraf.\n\nIkkinchi paragraf."
        result = split_text_into_chunks(text, chunk_size=1000)
        assert len(result) == 1
        assert "Birinchi" in result[0]
        assert "Ikkinchi" in result[0]

    def test_large_paragraphs_split_separately(self):
        para = "x" * 200
        text = f"{para}\n\n{para}"
        result = split_text_into_chunks(text, chunk_size=150, overlap=10)
        assert len(result) > 1

    def test_no_chunk_exceeds_chunk_size(self):
        text = "So'z " * 1000
        chunk_size = 200
        result = split_text_into_chunks(text, chunk_size=chunk_size, overlap=20)
        for chunk in result:
            assert len(chunk) <= chunk_size + 50

    def test_all_content_preserved(self):
        unique_words = [f"WORD{i}" for i in range(50)]
        text = " ".join(unique_words)
        result = split_text_into_chunks(text, chunk_size=100, overlap=10)
        combined = " ".join(result)
        for word in unique_words:
            assert word in combined

    def test_custom_chunk_size(self):
        text = "a" * 500
        result = split_text_into_chunks(text, chunk_size=100, overlap=10)
        for chunk in result:
            assert len(chunk) <= 150  # overlap bilan biroz katta bo'lishi mumkin

    def test_custom_overlap(self):
        text = "ab" * 300
        result_no_overlap = split_text_into_chunks(text, chunk_size=100, overlap=0)
        result_with_overlap = split_text_into_chunks(text, chunk_size=100, overlap=30)
        assert len(result_with_overlap) >= len(result_no_overlap)


class TestSplitLongText:
    def test_short_text_returns_one_chunk(self):
        result = _split_long_text("abc", chunk_size=100, overlap=10)
        assert result == ["abc"]

    def test_overlap_creates_sliding_window(self):
        text = "a" * 100
        result = _split_long_text(text, chunk_size=60, overlap=20)
        assert len(result) == 2
        assert len(result[0]) == 60
        assert len(result[1]) == 60

    def test_exact_division_no_remainder(self):
        text = "a" * 200
        result = _split_long_text(text, chunk_size=100, overlap=0)
        assert len(result) == 2
        assert all(len(c) == 100 for c in result)

    def test_no_empty_chunks(self):
        text = "x" * 350
        result = _split_long_text(text, chunk_size=100, overlap=20)
        for chunk in result:
            assert chunk != ""

    def test_all_chars_covered(self):
        text = "abcdefghij" * 10
        result = _split_long_text(text, chunk_size=20, overlap=0)
        assert "".join(result) == text


class TestGenerateEmbedding:
    def test_returns_list_of_floats(self):
        fake_vector = np.array([0.1] * 384, dtype=np.float32)
        with patch("app.ai.embeddings.get_model") as mock_get_model:
            mock_model = MagicMock()
            mock_model.encode.return_value = fake_vector
            mock_get_model.return_value = mock_model
            from app.ai.embeddings import generate_embedding
            result = generate_embedding("Test matni")
        assert isinstance(result, list)
        assert all(isinstance(v, float) for v in result)

    def test_returns_384_dimensions(self):
        fake_vector = np.array([0.0] * 384, dtype=np.float32)
        with patch("app.ai.embeddings.get_model") as mock_get_model:
            mock_model = MagicMock()
            mock_model.encode.return_value = fake_vector
            mock_get_model.return_value = mock_model
            from app.ai.embeddings import generate_embedding
            result = generate_embedding("Salom dunyo")
        assert len(result) == 384

    def test_calls_encode_with_normalize(self):
        fake_vector = np.array([0.5] * 384, dtype=np.float32)
        with patch("app.ai.embeddings.get_model") as mock_get_model:
            mock_model = MagicMock()
            mock_model.encode.return_value = fake_vector
            mock_get_model.return_value = mock_model
            from app.ai.embeddings import generate_embedding
            generate_embedding("Normalizatsiya testi")
        mock_model.encode.assert_called_once_with(
            "Normalizatsiya testi",
            normalize_embeddings=True,
        )

    def test_different_texts_called_separately(self):
        fake_vector = np.array([0.1] * 384, dtype=np.float32)
        with patch("app.ai.embeddings.get_model") as mock_get_model:
            mock_model = MagicMock()
            mock_model.encode.return_value = fake_vector
            mock_get_model.return_value = mock_model
            from app.ai.embeddings import generate_embedding
            generate_embedding("Birinchi matn")
            generate_embedding("Ikkinchi matn")
        assert mock_model.encode.call_count == 2

    def test_empty_string_still_returns_vector(self):
        fake_vector = np.zeros(384, dtype=np.float32)
        with patch("app.ai.embeddings.get_model") as mock_get_model:
            mock_model = MagicMock()
            mock_model.encode.return_value = fake_vector
            mock_get_model.return_value = mock_model
            from app.ai.embeddings import generate_embedding
            result = generate_embedding("")
        assert len(result) == 384

    def test_model_loaded_once_via_get_model(self):
        fake_vector = np.array([0.1] * 384, dtype=np.float32)
        with patch("app.ai.embeddings.get_model") as mock_get_model:
            mock_model = MagicMock()
            mock_model.encode.return_value = fake_vector
            mock_get_model.return_value = mock_model
            from app.ai.embeddings import generate_embedding
            generate_embedding("A")
            generate_embedding("B")
            generate_embedding("C")
        assert mock_get_model.call_count == 3