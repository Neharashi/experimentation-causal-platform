import io
import uuid
from collections import OrderedDict

import numpy as np
import pandas as pd

MAX_UPLOAD_BYTES = 50 * 1024 * 1024


class DatasetNotFound(KeyError):
    pass


class DatasetStore:
    """In-memory LRU store of uploaded / generated datasets."""

    def __init__(self, max_items: int = 30):
        self._items: OrderedDict[str, tuple[str, pd.DataFrame]] = OrderedDict()
        self.max_items = max_items

    def add(self, df: pd.DataFrame, name: str) -> str:
        if df.empty:
            raise ValueError("Dataset is empty.")
        dataset_id = uuid.uuid4().hex[:12]
        self._items[dataset_id] = (name, df.reset_index(drop=True))
        while len(self._items) > self.max_items:
            self._items.popitem(last=False)
        return dataset_id

    def add_csv(self, content: bytes, name: str) -> str:
        if len(content) > MAX_UPLOAD_BYTES:
            raise ValueError("File is larger than 50 MB.")
        try:
            df = pd.read_csv(io.BytesIO(content))
        except Exception as exc:
            raise ValueError(f"Could not parse CSV: {exc}") from exc
        df.columns = [str(c).strip() for c in df.columns]
        return self.add(df, name)

    def get(self, dataset_id: str) -> pd.DataFrame:
        if dataset_id not in self._items:
            raise DatasetNotFound(dataset_id)
        self._items.move_to_end(dataset_id)
        return self._items[dataset_id][1]

    def summary(self, dataset_id: str) -> dict:
        df = self.get(dataset_id)
        name = self._items[dataset_id][0]
        columns = []
        for col in df.columns:
            s = df[col]
            uniq = s.dropna().unique()
            columns.append({
                "name": col,
                "dtype": str(s.dtype),
                "is_numeric": bool(pd.api.types.is_numeric_dtype(s)),
                "n_unique": int(len(uniq)),
                "is_binary": bool(len(uniq) == 2),
                "sample_values": [to_jsonable(v) for v in uniq[:6]],
            })
        preview = df.head(8).replace({np.nan: None}).to_dict(orient="records")
        return {
            "dataset_id": dataset_id,
            "name": name,
            "rows": int(len(df)),
            "columns": columns,
            "preview": [{k: to_jsonable(v) for k, v in r.items()} for r in preview],
        }


def to_jsonable(v):
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return None if np.isnan(v) else float(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    return v


store = DatasetStore()
