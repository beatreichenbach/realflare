from __future__ import annotations
import dataclasses
import logging
import sys
import os
import json
from functools import partial
from importlib.resources import files
from typing import Any

from PySide2 import QtWidgets, QtCore, QtGui

from realflare.api.data import Flare, Render
from qt_extensions.elementbrowser import Field, ElementProxyModel
from qt_extensions.filebrowser import FileBrowser, FileElement
from qt_extensions.flexview import FlexView
from qt_extensions.icons import MaterialIcon
from qt_extensions.typeutils import cast
from realflare.storage import Storage


storage = Storage()


@dataclasses.dataclass
class FlareFileElement(FileElement):
    config: Flare | None = None
    thumbnail: str | None = None


@dataclasses.dataclass
class GhostFileElement(FileElement):
    config: Flare.Ghost | None = None
    thumbnail: str | None = None


@dataclasses.dataclass
class StarburstFileElement(FileElement):
    config: Flare.Starburst | None = None
    thumbnail: str | None = None


@dataclasses.dataclass
class QualityFileElement(FileElement):
    config: Render | None = None


class ThumbnailDelegate(QtWidgets.QStyledItemDelegate):
    def displayText(self, value: Any, locale: QtCore.QLocale) -> str:
        return ''

    # def paint(
    #     self,
    #     painter: QtGui.QPainter,
    #     option: QtWidgets.QStyleOptionViewItem,
    #     index: QtCore.QModelIndex,
    # ) -> None:
    #     logging.debug(option.rect.width())
    #     # option.decorationPosition = QtWidgets.QStyleOptionViewItem.Top
    #     super().paint(painter, option, index)

    # def drawDecoration(
    #     self,
    #     painter: QtGui.QPainter,
    #     option: QtWidgets.QStyleOptionViewItem,
    #     rect: QtCore.QRect,
    #     pixmap: QtGui.QPixmap,
    # ) -> None:
    #     logging.debug(rect.width())
    #     super().drawDecoration(painter, option, rect, pixmap)


class PresetBrowser(FileBrowser):
    load_requested: QtCore.Signal = QtCore.Signal(object)
    file_name = 'Unnamed.json'
    file_filter = '.json'

    def __init__(
        self,
        path: str = '',
        fields: list[Field] | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        if not path:
            path = storage.decode_path('$PRESET')

        self.root_dirs = {}
        for dir_name in ('flare', 'ghost', 'starburst'):
            root_path = storage.decode_path(os.path.join('$PRESET', dir_name))
            root_path = os.path.normpath(root_path)
            self.root_dirs[dir_name] = root_path

        # fields = [Field('name'), Field('thumbnail')]
        super().__init__(path, fields, parent)

        # self.flex = FlexView()
        # self.flex.setModel(self.proxy)
        # self.flex.column = 1
        # self.flex.grow = True
        #
        # splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        # splitter.addWidget(self.tree)
        # splitter.addWidget(self.flex)
        # self.layout().addWidget(splitter)

        self.tree.setItemDelegateForColumn(1, ThumbnailDelegate(self))
        # self.tree.setColumnHidden(1, True)

        self.tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu_request)

        self.remove_toolbar_action('add_element')
        self.remove_toolbar_action('duplicate_element')

    def _init_elements(self) -> None:
        # ensure root folders:
        for path in self.root_dirs.values():
            if not os.path.exists(path):
                os.makedirs(path)

        super()._init_elements()

    def _append_dir(self, path: str, parent: QtCore.QModelIndex) -> QtCore.QModelIndex:
        path = os.path.normpath(path)

        element = self._element(path)
        if type(element) == FileElement:
            return QtCore.QModelIndex()

        icon = MaterialIcon('folder')
        movable = path not in self.root_dirs.values()
        index = self.model.append_element(
            element, icon=icon, movable=movable, parent=parent
        )
        return index

    def _append_file(self, path: str, parent: QtCore.QModelIndex) -> QtCore.QModelIndex:
        # lens_model = cast(LensModel, data)
        # name = lens_model.name
        # image_path = str(files('realflare').joinpath('../docs/assets/images/flare.png'))
        # thumbnail = QtGui.QPixmap(image_path).scaledToWidth(
        #     200, QtCore.Qt.SmoothTransformation
        # )
        path = os.path.normpath(path)

        element = self._element(path)
        if type(element) == FileElement:
            return QtCore.QModelIndex()

        index = self.model.append_element(element, no_children=True, parent=parent)
        # thumbnail_index = index.siblingAtColumn(1)
        # item = self.model.itemFromIndex(thumbnail_index)
        # item.setData(thumbnail, QtCore.Qt.DecorationRole)
        return index

    def _element(self, path: str) -> FileElement:
        name = os.path.basename(path)

        try:
            data = storage.read_data(path) if os.path.isfile(path) else None
        except ValueError:
            data = None

        if path.startswith(self.root_dirs['flare']):
            config = cast(Flare, data) if data is not None else None
            element = FlareFileElement(name, path, config)
        elif path.startswith(self.root_dirs['ghost']):
            config = cast(Flare.Ghost, data) if data is not None else None
            element = GhostFileElement(name, path, config)
        elif path.startswith(self.root_dirs['starburst']):
            config = cast(Flare.Starburst, data) if data is not None else None
            element = StarburstFileElement(name, path, config)
        else:
            element = FileElement(name, path)

        return element

    def _context_menu_request(self, point: QtCore.QPoint) -> None:
        elements = self.selected_elements()
        if not elements:
            return

        element = elements[0]

        if not hasattr(element, 'config') or not element.config:
            return

        menu = QtWidgets.QMenu(self)
        action = QtWidgets.QAction('Load Preset', self)
        action.triggered.connect(partial(self.load_requested.emit, element.config))
        menu.addAction(action)
        position = self.tree.mapToGlobal(point)
        menu.exec_(position)

    # def filter(self, text: str) -> None:
    #     super().filter(text)
    #     self.flex.update()
