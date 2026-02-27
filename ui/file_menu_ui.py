# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'file_menu.ui'
##
## Created by: Qt User Interface Compiler version 6.10.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QFrame, QPushButton, QSizePolicy,
    QVBoxLayout, QWidget)

class Ui_Form(object):
    def setupUi(self, Form):
        if not Form.objectName():
            Form.setObjectName(u"Form")
        Form.resize(180, 226)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(Form.sizePolicy().hasHeightForWidth())
        Form.setSizePolicy(sizePolicy)
        Form.setMinimumSize(QSize(180, 0))
        Form.setMaximumSize(QSize(180, 16777215))
        Form.setStyleSheet(u"")
        self.verticalLayout_2 = QVBoxLayout(Form)
        self.verticalLayout_2.setSpacing(0)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.file_menu = QFrame(Form)
        self.file_menu.setObjectName(u"file_menu")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.file_menu.sizePolicy().hasHeightForWidth())
        self.file_menu.setSizePolicy(sizePolicy1)
        self.file_menu.setStyleSheet(u"")
        self.file_menu.setFrameShape(QFrame.Shape.NoFrame)
        self.file_menu.setFrameShadow(QFrame.Shadow.Plain)
        self.verticalLayout = QVBoxLayout(self.file_menu)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.btn_new = QPushButton(self.file_menu)
        self.btn_new.setObjectName(u"btn_new")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.btn_new.sizePolicy().hasHeightForWidth())
        self.btn_new.setSizePolicy(sizePolicy2)
        self.btn_new.setMinimumSize(QSize(0, 32))
        self.btn_new.setMaximumSize(QSize(16777215, 32))

        self.verticalLayout.addWidget(self.btn_new)

        self.btn_open = QPushButton(self.file_menu)
        self.btn_open.setObjectName(u"btn_open")
        sizePolicy2.setHeightForWidth(self.btn_open.sizePolicy().hasHeightForWidth())
        self.btn_open.setSizePolicy(sizePolicy2)
        self.btn_open.setMinimumSize(QSize(0, 32))
        self.btn_open.setMaximumSize(QSize(16777215, 32))

        self.verticalLayout.addWidget(self.btn_open)

        self.btn_save = QPushButton(self.file_menu)
        self.btn_save.setObjectName(u"btn_save")
        sizePolicy2.setHeightForWidth(self.btn_save.sizePolicy().hasHeightForWidth())
        self.btn_save.setSizePolicy(sizePolicy2)
        self.btn_save.setMinimumSize(QSize(0, 32))
        self.btn_save.setMaximumSize(QSize(16777215, 32))

        self.verticalLayout.addWidget(self.btn_save)

        self.btn_save_as = QPushButton(self.file_menu)
        self.btn_save_as.setObjectName(u"btn_save_as")
        sizePolicy2.setHeightForWidth(self.btn_save_as.sizePolicy().hasHeightForWidth())
        self.btn_save_as.setSizePolicy(sizePolicy2)
        self.btn_save_as.setMinimumSize(QSize(0, 32))
        self.btn_save_as.setMaximumSize(QSize(16777215, 32))

        self.verticalLayout.addWidget(self.btn_save_as)

        self.btn_close = QPushButton(self.file_menu)
        self.btn_close.setObjectName(u"btn_close")
        sizePolicy2.setHeightForWidth(self.btn_close.sizePolicy().hasHeightForWidth())
        self.btn_close.setSizePolicy(sizePolicy2)
        self.btn_close.setMinimumSize(QSize(0, 32))
        self.btn_close.setMaximumSize(QSize(16777215, 32))

        self.verticalLayout.addWidget(self.btn_close)

        self.btn_exit = QPushButton(self.file_menu)
        self.btn_exit.setObjectName(u"btn_exit")
        sizePolicy2.setHeightForWidth(self.btn_exit.sizePolicy().hasHeightForWidth())
        self.btn_exit.setSizePolicy(sizePolicy2)
        self.btn_exit.setMinimumSize(QSize(0, 32))
        self.btn_exit.setMaximumSize(QSize(16777215, 32))

        self.verticalLayout.addWidget(self.btn_exit)


        self.verticalLayout_2.addWidget(self.file_menu)


        self.retranslateUi(Form)

        QMetaObject.connectSlotsByName(Form)
    # setupUi

    def retranslateUi(self, Form):
        Form.setWindowTitle(QCoreApplication.translate("Form", u"Form", None))
        self.btn_new.setText(QCoreApplication.translate("Form", u"\u65b0\u5efa", None))
        self.btn_open.setText(QCoreApplication.translate("Form", u"\u6253\u5f00", None))
        self.btn_save.setText(QCoreApplication.translate("Form", u"\u4fdd\u5b58", None))
        self.btn_save_as.setText(QCoreApplication.translate("Form", u"\u53e6\u5b58\u4e3a", None))
        self.btn_close.setText(QCoreApplication.translate("Form", u"\u5173\u95ed", None))
        self.btn_exit.setText(QCoreApplication.translate("Form", u"\u9000\u51fa", None))
    # retranslateUi

