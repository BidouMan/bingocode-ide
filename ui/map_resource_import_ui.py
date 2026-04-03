# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'map_resource_import.ui'
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
from PySide6.QtWidgets import (QApplication, QComboBox, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QRadioButton,
    QSizePolicy, QSpacerItem, QVBoxLayout, QWidget)

class Ui_Form(object):
    def setupUi(self, Form):
        if not Form.objectName():
            Form.setObjectName(u"Form")
        Form.resize(380, 160)
        Form.setMinimumSize(QSize(320, 160))
        Form.setMaximumSize(QSize(380, 200))
        self.verticalLayout_2 = QVBoxLayout(Form)
        self.verticalLayout_2.setSpacing(0)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(20, 0, 20, 0)
        self.widget_4 = QWidget(Form)
        self.widget_4.setObjectName(u"widget_4")
        self.widget_4.setMinimumSize(QSize(320, 160))
        self.widget_4.setMaximumSize(QSize(320, 160))
        self.verticalLayout = QVBoxLayout(self.widget_4)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.widget = QWidget(self.widget_4)
        self.widget.setObjectName(u"widget")
        self.widget.setMinimumSize(QSize(300, 0))
        self.widget.setMaximumSize(QSize(300, 16777215))
        self.horizontalLayout = QHBoxLayout(self.widget)
        self.horizontalLayout.setSpacing(4)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel(self.widget)
        self.label.setObjectName(u"label")

        self.horizontalLayout.addWidget(self.label)

        self.import_res_path = QLineEdit(self.widget)
        self.import_res_path.setObjectName(u"import_res_path")
        self.import_res_path.setFrame(True)
        self.import_res_path.setEchoMode(QLineEdit.EchoMode.Normal)

        self.horizontalLayout.addWidget(self.import_res_path)

        self.btn_browse = QPushButton(self.widget)
        self.btn_browse.setObjectName(u"btn_browse")

        self.horizontalLayout.addWidget(self.btn_browse)


        self.verticalLayout.addWidget(self.widget, 0, Qt.AlignmentFlag.AlignHCenter)

        self.widget_2 = QWidget(self.widget_4)
        self.widget_2.setObjectName(u"widget_2")
        self.widget_2.setMinimumSize(QSize(300, 0))
        self.widget_2.setMaximumSize(QSize(300, 16777215))
        self.horizontalLayout_3 = QHBoxLayout(self.widget_2)
        self.horizontalLayout_3.setSpacing(0)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.horizontalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.groupBox = QGroupBox(self.widget_2)
        self.groupBox.setObjectName(u"groupBox")
        self.horizontalLayout_2 = QHBoxLayout(self.groupBox)
        self.horizontalLayout_2.setSpacing(0)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.radioButton_image = QRadioButton(self.groupBox)
        self.radioButton_image.setObjectName(u"radioButton_image")
        self.radioButton_image.setChecked(True)

        self.horizontalLayout_2.addWidget(self.radioButton_image)

        self.radioButton_tileset = QRadioButton(self.groupBox)
        self.radioButton_tileset.setObjectName(u"radioButton_tileset")

        self.horizontalLayout_2.addWidget(self.radioButton_tileset)


        self.horizontalLayout_3.addWidget(self.groupBox)

        self.horizontalSpacer_3 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_3.addItem(self.horizontalSpacer_3)

        self.label_2 = QLabel(self.widget_2)
        self.label_2.setObjectName(u"label_2")

        self.horizontalLayout_3.addWidget(self.label_2)

        self.comboBox_size = QComboBox(self.widget_2)
        self.comboBox_size.addItem("")
        self.comboBox_size.addItem("")
        self.comboBox_size.addItem("")
        self.comboBox_size.setObjectName(u"comboBox_size")
        self.comboBox_size.setEditable(True)

        self.horizontalLayout_3.addWidget(self.comboBox_size)

        self.horizontalLayout_3.setStretch(0, 2)
        self.horizontalLayout_3.setStretch(3, 1)

        self.verticalLayout.addWidget(self.widget_2, 0, Qt.AlignmentFlag.AlignHCenter)

        self.widget_3 = QWidget(self.widget_4)
        self.widget_3.setObjectName(u"widget_3")
        self.widget_3.setMinimumSize(QSize(300, 0))
        self.widget_3.setMaximumSize(QSize(300, 16777215))
        self.horizontalLayout_4 = QHBoxLayout(self.widget_3)
        self.horizontalLayout_4.setSpacing(4)
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.horizontalLayout_4.setContentsMargins(0, 0, 0, 0)
        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_4.addItem(self.horizontalSpacer)

        self.btn_no = QPushButton(self.widget_3)
        self.btn_no.setObjectName(u"btn_no")

        self.horizontalLayout_4.addWidget(self.btn_no)

        self.btn_ok = QPushButton(self.widget_3)
        self.btn_ok.setObjectName(u"btn_ok")

        self.horizontalLayout_4.addWidget(self.btn_ok)

        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_4.addItem(self.horizontalSpacer_2)


        self.verticalLayout.addWidget(self.widget_3, 0, Qt.AlignmentFlag.AlignHCenter)

        self.verticalLayout.setStretch(0, 1)
        self.verticalLayout.setStretch(1, 1)
        self.verticalLayout.setStretch(2, 1)

        self.verticalLayout_2.addWidget(self.widget_4, 0, Qt.AlignmentFlag.AlignHCenter)


        self.retranslateUi(Form)

        QMetaObject.connectSlotsByName(Form)
    # setupUi

    def retranslateUi(self, Form):
        Form.setWindowTitle(QCoreApplication.translate("Form", u"Form", None))
        self.label.setText(QCoreApplication.translate("Form", u"\u8d44\u6e90\u8def\u5f84:", None))
        self.btn_browse.setText(QCoreApplication.translate("Form", u"\u6d4f\u89c8", None))
        self.groupBox.setTitle("")
        self.radioButton_image.setText(QCoreApplication.translate("Form", u"\u56fe\u50cf\u6a21\u5f0f", None))
        self.radioButton_tileset.setText(QCoreApplication.translate("Form", u"\u56fe\u5757\u96c6\u5408", None))
        self.label_2.setText(QCoreApplication.translate("Form", u"\u5c3a\u5bf8:", None))
        self.comboBox_size.setItemText(0, QCoreApplication.translate("Form", u"16x16", None))
        self.comboBox_size.setItemText(1, QCoreApplication.translate("Form", u"32x32", None))
        self.comboBox_size.setItemText(2, QCoreApplication.translate("Form", u"64x64", None))

        self.btn_no.setText(QCoreApplication.translate("Form", u"\u53d6\u6d88", None))
        self.btn_ok.setText(QCoreApplication.translate("Form", u"\u786e\u5b9a", None))
    # retranslateUi

