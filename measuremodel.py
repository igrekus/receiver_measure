from PyQt5.QtCore import Qt, QAbstractTableModel, QVariant


class MeasureModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._header = list()
        self._data = list()

    def update(self, header, data):
        self.beginResetModel()
        self._header = header
        self._data = data
        self.endResetModel()

    def headerData(self, section, orientation, role=None):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                if section < len(self._header):
                    return QVariant(self._header[section])
        return QVariant()

    def rowCount(self, parent=None, *args, **kwargs):
        if parent.isValid():
            return 0
        return 1

    def columnCount(self, parent=None, *args, **kwargs):
        return len(self._header)

    def data(self, index, role=None):
        if not index.isValid():
            return QVariant()
        if role == Qt.DisplayRole:
            try:
                return QVariant(self._data[index.column()])
            except LookupError:
                return QVariant()
        return QVariant()
