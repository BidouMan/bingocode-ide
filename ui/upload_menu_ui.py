# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'upload_menu.ui'
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
import resources_rc

class Ui_upload_menu(object):
    def setupUi(self, upload_menu):
        if not upload_menu.objectName():
            upload_menu.setObjectName(u"upload_menu")
        upload_menu.resize(70, 226)
        upload_menu.setMinimumSize(QSize(50, 226))
        upload_menu.setMaximumSize(QSize(70, 16777215))
        self.btn_upload = QPushButton(upload_menu)
        self.btn_upload.setObjectName(u"btn_upload")
        self.btn_upload.setGeometry(QRect(10, 176, 50, 50))
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.btn_upload.sizePolicy().hasHeightForWidth())
        self.btn_upload.setSizePolicy(sizePolicy)
        self.btn_upload.setMinimumSize(QSize(50, 50))
        self.btn_upload.setMaximumSize(QSize(50, 50))
        self.btn_upload.setStyleSheet(u"QPushButton#btn_upload {\n"
"    background-color: transparent;\n"
"    border: none;\n"
"    padding: 0px;\n"
"    margin: 0px;\n"
"}")
        icon = QIcon()
        icon.addFile(u":/icons/sprite_upload.svg", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.btn_upload.setIcon(icon)
        self.btn_upload.setIconSize(QSize(40, 40))
        self.btn_upload.setFlat(True)
        self.menu_frame = QFrame(upload_menu)
        self.menu_frame.setObjectName(u"menu_frame")
        self.menu_frame.setEnabled(True)
        self.menu_frame.setGeometry(QRect(20, 10, 30, 150))
        self.menu_frame.setMinimumSize(QSize(30, 150))
        self.menu_frame.setMaximumSize(QSize(30, 16777215))
        self.menu_frame.setStyleSheet(u"/* 1. \u83dc\u5355\u4e3b\u4f53\uff1a\u6781\u81f4\u7626\u8eab\u540e\u7684\u80f6\u56ca\u98ce\u683c */\n"
"QFrame#menu_frame {\n"
"    /* \u4f7f\u7528\u4f60\u6307\u5b9a\u7684\u54c1\u724c\u7eff */\n"
"    background-color: #53AA66; \n"
"    \n"
"    /* 30px \u5bbd\u5ea6\u7684\u5706\u89d2\u534a\u5f84\u5e94\u4e3a 15px \u624d\u80fd\u5f62\u6210\u6b63\u5706\u534a\u5706 */\n"
"    border-top-left-radius: 15px;\n"
"    border-top-right-radius: 15px;\n"
"    \n"
"    /* \u5e95\u90e8\u4e5f\u8bbe\u4e3a\u5706\u89d2\uff0c\u589e\u52a0\u60ac\u6d6e\u611f */\n"
"    border-bottom-left-radius: 15px;\n"
"    border-bottom-right-radius: 15px;\n"
"    \n"
"    border: none;\n"
"}\n"
"\n"
"/* 2. \u5185\u90e8\u6309\u94ae\uff1a\u9488\u5bf9 20px \u56fe\u6807\u4f18\u5316 */\n"
"QFrame#menu_frame QPushButton {\n"
"    background-color: transparent;\n"
"    border: none;\n"
"    /* \u6781\u81f4\u7d27\u51d1\u7684\u8fb9\u8ddd */\n"
"    padding: 6px 0px; \n"
"    margin: 0px;\n"
"}\n"
"\n"
"/* 3. \u6309\u94ae\u60ac\u505c\uff1a\u6de1\u767d\u8272"
                        "\u9ad8\u4eae */\n"
"QFrame#menu_frame QPushButton:hover {\n"
"    background-color: rgba(255, 255, 255, 0.4);\n"
"    /* \u60ac\u505c\u9ad8\u4eae\u4e5f\u8981\u505a\u6210\u5706\u89d2\uff0c\u9002\u914d 30px \u5bbd\u5ea6 */\n"
"    border-radius: 12px;\n"
"}\n"
"\n"
"/* 4. \u7ad9\u4f4d\u5bb9\u5668\uff1a\u8bbe\u4e3a\u540c\u6837\u7684\u7eff\u8272\uff0c\u5b9e\u73b0\u5b8c\u7f8e\u91cd\u53e0 */\n"
"QWidget#widget {\n"
"    background-color: #53AA66;\n"
"    /* \u5e95\u90e8\u5706\u89d2\u5fc5\u987b\u548c\u7236\u5bb9\u5668\u4e00\u81f4 */\n"
"    border-bottom-left-radius: 15px;\n"
"    border-bottom-right-radius: 15px;\n"
"    border: none;\n"
"}")
        self.menu_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.menu_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.verticalLayout = QVBoxLayout(self.menu_frame)
        self.verticalLayout.setSpacing(1)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.btn_import = QPushButton(self.menu_frame)
        self.btn_import.setObjectName(u"btn_import")
        icon1 = QIcon()
        icon1.addFile(u":/icons/icon--file-upload.svg", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.btn_import.setIcon(icon1)
        self.btn_import.setIconSize(QSize(20, 20))

        self.verticalLayout.addWidget(self.btn_import)

        self.btn_paint = QPushButton(self.menu_frame)
        self.btn_paint.setObjectName(u"btn_paint")
        icon2 = QIcon()
        icon2.addFile(u":/icons/icon--paint.svg", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.btn_paint.setIcon(icon2)
        self.btn_paint.setIconSize(QSize(20, 20))

        self.verticalLayout.addWidget(self.btn_paint)

        self.btn_open = QPushButton(self.menu_frame)
        self.btn_open.setObjectName(u"btn_open")
        icon3 = QIcon()
        icon3.addFile(u":/icons/icon--select--sprite.svg", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.btn_open.setIcon(icon3)
        self.btn_open.setIconSize(QSize(20, 20))

        self.verticalLayout.addWidget(self.btn_open)

        self.widget = QWidget(self.menu_frame)
        self.widget.setObjectName(u"widget")
        self.widget.setMinimumSize(QSize(30, 50))
        self.widget.setMaximumSize(QSize(30, 50))

        self.verticalLayout.addWidget(self.widget)

        self.verticalLayout.setStretch(0, 1)
        self.verticalLayout.setStretch(1, 1)
        self.verticalLayout.setStretch(2, 1)
        self.verticalLayout.setStretch(3, 1)
        self.menu_frame.raise_()
        self.btn_upload.raise_()

        self.retranslateUi(upload_menu)

        QMetaObject.connectSlotsByName(upload_menu)
    # setupUi

    def retranslateUi(self, upload_menu):
        upload_menu.setWindowTitle(QCoreApplication.translate("upload_menu", u"Form", None))
        self.btn_upload.setText("")
        self.btn_import.setText("")
        self.btn_paint.setText("")
        self.btn_open.setText("")
    # retranslateUi

