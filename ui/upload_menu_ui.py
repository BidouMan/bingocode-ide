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
    QSpacerItem, QVBoxLayout, QWidget)
import resources_rc

class Ui_upload_menu(object):
    def setupUi(self, upload_menu):
        if not upload_menu.objectName():
            upload_menu.setObjectName(u"upload_menu")
        upload_menu.resize(70, 226)
        upload_menu.setMinimumSize(QSize(50, 226))
        upload_menu.setMaximumSize(QSize(70, 16777215))
        self.verticalLayout_2 = QVBoxLayout(upload_menu)
        self.verticalLayout_2.setSpacing(0)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_2.addItem(self.verticalSpacer)

        self.menu_frame = QFrame(upload_menu)
        self.menu_frame.setObjectName(u"menu_frame")
        self.menu_frame.setEnabled(True)
        self.menu_frame.setMinimumSize(QSize(30, 0))
        self.menu_frame.setMaximumSize(QSize(30, 16777215))
        self.menu_frame.setStyleSheet(u"#menu_frame {\n"
"    /* \u8bbe\u7f6e\u80cc\u666f\u8272\uff0c\u8fd9\u91cc\u7528\u4e86\u4e00\u4e2a\u6df1\u7070\u8272\uff0c\u4f60\u53ef\u4ee5\u6362\u6210\u4f60\u559c\u6b22\u7684\u989c\u8272 */\n"
"    background-color: #4B9B5C; \n"
"    \n"
"    /* \u9876\u90e8\u5706\u89d2\u8bbe\u7f6e\uff1a\u5de6\u4e0a, \u53f3\u4e0a, \u53f3\u4e0b, \u5de6\u4e0b */\n"
"    /* \u5bbd\u5ea630px\uff0c\u534a\u5f84\u5efa\u8bae\u8bbe\u4e3a 15px\uff0c\u521a\u597d\u662f\u4e00\u4e2a\u5b8c\u7f8e\u7684\u534a\u5706\u9876 */\n"
"    border-top-left-radius: 15px;\n"
"    border-top-right-radius: 15px;\n"
"    border-bottom-left-radius: 0px;\n"
"    border-bottom-right-radius: 0px;\n"
"\n"
"    /* \u53ef\u9009\uff1a\u5982\u679c\u80cc\u666f\u8272\u592a\u6697\uff0c\u52a0\u4e2a\u7ec6\u8fb9\u6846\u5206\u754c */\n"
"   \n"
"    border-bottom: none; /* \u5e95\u90e8\u4e0d\u8981\u8fb9\u6846\uff0c\u65b9\u4fbf\u548c\u6309\u94ae\u5bf9\u63a5 */\n"
"}")
        self.menu_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.menu_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.verticalLayout = QVBoxLayout(self.menu_frame)
        self.verticalLayout.setSpacing(4)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 4, 0, 0)
        self.btn_import = QPushButton(self.menu_frame)
        self.btn_import.setObjectName(u"btn_import")
        self.btn_import.setMinimumSize(QSize(0, 30))
        self.btn_import.setMaximumSize(QSize(16777215, 30))
        icon = QIcon()
        icon.addFile(u":/icons/icon--file-upload.svg", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.btn_import.setIcon(icon)
        self.btn_import.setIconSize(QSize(20, 20))
        self.btn_import.setFlat(True)

        self.verticalLayout.addWidget(self.btn_import)

        self.btn_paint = QPushButton(self.menu_frame)
        self.btn_paint.setObjectName(u"btn_paint")
        self.btn_paint.setMinimumSize(QSize(0, 30))
        self.btn_paint.setMaximumSize(QSize(16777215, 30))
        icon1 = QIcon()
        icon1.addFile(u":/icons/icon--paint.svg", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.btn_paint.setIcon(icon1)
        self.btn_paint.setIconSize(QSize(20, 20))
        self.btn_paint.setFlat(True)

        self.verticalLayout.addWidget(self.btn_paint)

        self.btn_open = QPushButton(self.menu_frame)
        self.btn_open.setObjectName(u"btn_open")
        self.btn_open.setMinimumSize(QSize(0, 30))
        self.btn_open.setMaximumSize(QSize(16777215, 30))
        icon2 = QIcon()
        icon2.addFile(u":/icons/icon--select--sprite.svg", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.btn_open.setIcon(icon2)
        self.btn_open.setIconSize(QSize(20, 20))
        self.btn_open.setFlat(True)

        self.verticalLayout.addWidget(self.btn_open)

        self.verticalSpacer_2 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout.addItem(self.verticalSpacer_2)


        self.verticalLayout_2.addWidget(self.menu_frame, 0, Qt.AlignmentFlag.AlignHCenter)

        self.btn_upload = QPushButton(upload_menu)
        self.btn_upload.setObjectName(u"btn_upload")
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
        icon3 = QIcon()
        icon3.addFile(u":/icons/sprite_upload.svg", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.btn_upload.setIcon(icon3)
        self.btn_upload.setIconSize(QSize(40, 40))
        self.btn_upload.setFlat(True)

        self.verticalLayout_2.addWidget(self.btn_upload, 0, Qt.AlignmentFlag.AlignHCenter)


        self.retranslateUi(upload_menu)

        QMetaObject.connectSlotsByName(upload_menu)
    # setupUi

    def retranslateUi(self, upload_menu):
        upload_menu.setWindowTitle(QCoreApplication.translate("upload_menu", u"Form", None))
        self.btn_import.setText("")
        self.btn_paint.setText("")
        self.btn_open.setText("")
        self.btn_upload.setText("")
    # retranslateUi

