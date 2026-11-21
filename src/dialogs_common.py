"""Shared helpers for the app dialogs."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QRect
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtWidgets import (
    QComboBox, QCompleter, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QDialog, QFormLayout, QLineEdit, QTextEdit, QMessageBox, QScrollArea, QFrame, QSizePolicy,
)

from . import util


def fill_item_completer(combo, items):
    names = [it.name for it in items]
    completer = QCompleter(names)
    completer.setCaseSensitivity(Qt.CaseInsensitive)
    completer.setFilterMode(Qt.MatchContains)
    combo.setCompleter(completer)
    combo.setEditable(True)


def resolve_item_name(name, items):
    if not name:
        return None
    key = name.strip().lower()
    for it in items:
        if it.name.lower() == key:
            return it
    return None


def show_error(parent, title, message):
    QMessageBox.critical(parent, title, message)


def image_preview(path, size=48):
    pix = QPixmap()
    if path:
        pix = QPixmap(path)
    label = QLabel()
    label.setFixedSize(size, size)
    label.setStyleSheet('border: 1px solid #2b313c; border-radius: 6px; background: #181b21;')
    label.setText('＋' if not path else '')
    label.setAlignment(Qt.AlignCenter)
    label.setStyleSheet('border: 1px solid #2b313c; border-radius: 6px; background: #181b21; color: #7c8594;')
    if not pix.isNull():
        scaled = pix.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        label.setPixmap(scaled)
    return label


def thumbnail(parent, path, size=64):
    label = QLabel(parent)
    label.setFixedSize(size, size)
    label.setAlignment(Qt.AlignCenter)
    label.setStyleSheet('border: 1px solid #2b313c; border-radius: 8px; background: #181b21;')
    pix = QPixmap()
    if path:
        pix = QPixmap(path)
    if not pix.isNull():
        scaled = pix.scaled(size - 10, size - 10, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        label.setPixmap(scaled)
    else:
        label.setText('?')
        label.setStyleSheet('border: 1px dashed #2b313c; border-radius: 8px; background: #181b21; color: #7c8594; font-size: 20px;')
    return label


def groups_label(text):
    l = QLabel(text)
    l.setStyleSheet('color: #9aa3b2; font-weight: 700; letter-spacing: 1.2px; font-size: 11px; margin-top: 8px;')
    return l


def separator():
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setFrameShadow(QFrame.Sunken)
    line.setStyleSheet('color: #2b313c; background: #2b313c; border: 0; max-width: 100%;')
    return line


def chip(text, color='#2c313b', text_color='#aab2c2'):
    label = QLabel(text)
    label.setStyleSheet(f'padding: 3px 9px; border-radius: 9px; background: {color}; color: {text_color}; font-size: 11px; font-weight: 600;')
    label.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
    return label
