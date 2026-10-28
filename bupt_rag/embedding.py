import numpy as np

from .models import AppError


class BGEEncoder:
    def __init__(self, settings):
        self.name = settings.embedding_model
        self.revision = settings.embedding_revision
        self.identity = f"sentence-transformers:{self.name}@{self.revision}:normalized:v1"
        self._model = None

    @property
    def model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                try:
                    self._model = SentenceTransformer(
                        self.name,
                        revision=self.revision,
                        device="cpu",
                        trust_remote_code=False,
                        local_files_only=True,
                    )
                except OSError:
                    self._model = SentenceTransformer(
                        self.name, revision=self.revision, device="cpu", trust_remote_code=False
                    )
                self._model.max_seq_length = 512
            except Exception as exc:
                raise AppError("model_unavailable", "BGE 模型无法加载；请按 README 下载模型后重试。") from exc
        return self._model

    def token_length(self, text):
        return len(self.model.tokenizer.encode(text, add_special_tokens=True, truncation=False))

    def encode(self, texts, query=False):
        if query:
            texts = ["为这个句子生成表示以用于检索相关文章：" + text for text in texts]
        try:
            return np.asarray(
                self.model.encode(texts, batch_size=16, normalize_embeddings=True, show_progress_bar=False),
                dtype=np.float32,
            )
        except AppError:
            raise
        except Exception as exc:
            raise AppError("model_unavailable", "向量编码失败；现有知识快照不变。") from exc
