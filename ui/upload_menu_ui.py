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
        upload_menu.resize(70, 116)
        upload_menu.setMinimumSize(QSize(50, 50))
        upload_menu.setMaximumSize(QSize(70, 116))
        self.verticalLayout_3 = QVBoxLayout(upload_menu)
        self.verticalLayout_3.setSpacing(0)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.verticalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.all_frame = QFrame(upload_menu)
        self.all_frame.setObjectName(u"all_frame")
        self.all_frame.setFrameShape(QFrame.Shape.NoFrame)
        self.all_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.verticalLayout_2 = QVBoxLayout(self.all_frame)
        self.verticalLayout_2.setSpacing(0)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.menu_frame = QFrame(self.all_frame)
        self.menu_frame.setObjectName(u"menu_frame")
        self.menu_frame.setEnabled(False)
        self.menu_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.menu_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.verticalLayout = QVBoxLayout(self.menu_frame)
        self.verticalLayout.setSpacing(20)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.btn_sprite = QPushButton(self.menu_frame)
        self.btn_sprite.setObjectName(u"btn_sprite")

        self.verticalLayout.addWidget(self.btn_sprite)

        self.btn_bg = QPushButton(self.menu_frame)
        self.btn_bg.setObjectName(u"btn_bg")

        self.verticalLayout.addWidget(self.btn_bg)

        self.btn_sound = QPushButton(self.menu_frame)
        self.btn_sound.setObjectName(u"btn_sound")

        self.verticalLayout.addWidget(self.btn_sound)


        self.verticalLayout_2.addWidget(self.menu_frame)

        self.btn_upload = QPushButton(self.all_frame)
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
        icon = QIcon()
        icon.addFile(u":/icons/sprite_upload.svg", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.btn_upload.setIcon(icon)
        self.btn_upload.setIconSize(QSize(40, 40))
        self.btn_upload.setFlat(True)

        self.verticalLayout_2.addWidget(self.btn_upload, 0, Qt.AlignmentFlag.AlignHCenter|Qt.AlignmentFlag.AlignVCenter)


        self.verticalLayout_3.addWidget(self.all_frame, 0, Qt.AlignmentFlag.AlignBottom)


        self.retranslateUi(upload_menu)

        QMetaObject.connectSlotsByName(upload_menu)
    # setupUi

    def retranslateUi(self, upload_menu):
        upload_menu.setWindowTitle(QCoreApplication.translate("upload_menu", u"Form", None))
        self.btn_sprite.setText(QCoreApplication.translate("upload_menu", u"\u89d2\u8272", None))
        self.btn_bg.setText(QCoreApplication.translate("upload_menu", u"\u58f0\u97f3", None))
        self.btn_sound.setText(QCoreApplication.translate("upload_menu", u"\u80cc\u666f", None))
        self.btn_upload.setText("")
    # retranslateUi

