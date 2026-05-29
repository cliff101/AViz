"""QListWidget internal drag-and-drop reorder helpers."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QListWidget


def enable_internal_drag_reorder(
    list_widget: QListWidget,
    on_reordered: Callable[[], None],
) -> None:
    """Ctrl+drag is not required — drag rows to reorder (Qt built-in InternalMove)."""
    list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
    list_widget.setDefaultDropAction(Qt.DropAction.MoveAction)
    list_widget.setDragEnabled(True)
    list_widget.setAcceptDrops(True)
    list_widget.setDropIndicatorShown(True)
    list_widget.model().rowsMoved.connect(lambda *_args: on_reordered())


def file_ids_from_list(list_widget: QListWidget, *, role: int = 256) -> list[str]:
    ids: list[str] = []
    for i in range(list_widget.count()):
        item = list_widget.item(i)
        if item is None:
            continue
        fid = item.data(role)
        if fid:
            ids.append(str(fid))
    return ids
