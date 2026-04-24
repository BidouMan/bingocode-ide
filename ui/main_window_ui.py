# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'main_window.ui'
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
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QButtonGroup, QCheckBox,
    QComboBox, QFrame, QGraphicsView, QGridLayout,
    QHBoxLayout, QHeaderView, QLabel, QLayout,
    QLineEdit, QListView, QListWidget, QListWidgetItem,
    QPlainTextEdit, QPushButton, QSizePolicy, QSlider,
    QSpacerItem, QSplitter, QStackedWidget, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget)
import resources_rc

class Ui_Form(object):
    def setupUi(self, Form):
        if not Form.objectName():
            Form.setObjectName(u"Form")
        Form.resize(1078, 718)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(Form.sizePolicy().hasHeightForWidth())
        Form.setSizePolicy(sizePolicy)
        Form.setMinimumSize(QSize(640, 480))
        self.verticalLayout_4 = QVBoxLayout(Form)
        self.verticalLayout_4.setSpacing(0)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.verticalLayout_4.setContentsMargins(0, 0, 0, 0)
        self.change_page = QStackedWidget(Form)
        self.change_page.setObjectName(u"change_page")
        self.change_page.setMaximumSize(QSize(16777215, 16777215))
        self.edit_stage_frame = QWidget()
        self.edit_stage_frame.setObjectName(u"edit_stage_frame")
        self.verticalLayout_19 = QVBoxLayout(self.edit_stage_frame)
        self.verticalLayout_19.setSpacing(0)
        self.verticalLayout_19.setObjectName(u"verticalLayout_19")
        self.verticalLayout_19.setContentsMargins(0, 0, 0, 0)
        self.menu_frame = QFrame(self.edit_stage_frame)
        self.menu_frame.setObjectName(u"menu_frame")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.menu_frame.sizePolicy().hasHeightForWidth())
        self.menu_frame.setSizePolicy(sizePolicy1)
        self.menu_frame.setMinimumSize(QSize(0, 40))
        self.menu_frame.setMaximumSize(QSize(16777215, 40))
        self.menu_frame.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.menu_frame.setStyleSheet(u"")
        self.menu_frame.setFrameShape(QFrame.Shape.NoFrame)
        self.menu_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.menu_frame.setLineWidth(0)
        self.horizontalLayout_3 = QHBoxLayout(self.menu_frame)
        self.horizontalLayout_3.setSpacing(5)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.horizontalLayout_3.setContentsMargins(0, 0, 5, 0)
        self.btn_logo = QPushButton(self.menu_frame)
        self.btn_logo.setObjectName(u"btn_logo")
        self.btn_logo.setEnabled(True)
        sizePolicy.setHeightForWidth(self.btn_logo.sizePolicy().hasHeightForWidth())
        self.btn_logo.setSizePolicy(sizePolicy)
        self.btn_logo.setMinimumSize(QSize(60, 39))
        self.btn_logo.setMaximumSize(QSize(60, 39))
        self.btn_logo.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        icon = QIcon()
        icon.addFile(u":/icons/logo.svg", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.btn_logo.setIcon(icon)
        self.btn_logo.setIconSize(QSize(90, 40))
        self.btn_logo.setFlat(False)

        self.horizontalLayout_3.addWidget(self.btn_logo, 0, Qt.AlignmentFlag.AlignTop)

        self.btn_file = QPushButton(self.menu_frame)
        self.btn_file.setObjectName(u"btn_file")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.btn_file.sizePolicy().hasHeightForWidth())
        self.btn_file.setSizePolicy(sizePolicy2)
        self.btn_file.setMinimumSize(QSize(0, 0))
        self.btn_file.setMaximumSize(QSize(16777215, 40))
        self.btn_file.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        icon1 = QIcon()
        icon1.addFile(u":/icons/icon--file.svg", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.btn_file.setIcon(icon1)
        self.btn_file.setIconSize(QSize(18, 18))
        self.btn_file.setFlat(False)

        self.horizontalLayout_3.addWidget(self.btn_file)

        self.btn_code_editor = QPushButton(self.menu_frame)
        self.btn_code_editor.setObjectName(u"btn_code_editor")
        sizePolicy2.setHeightForWidth(self.btn_code_editor.sizePolicy().hasHeightForWidth())
        self.btn_code_editor.setSizePolicy(sizePolicy2)
        self.btn_code_editor.setMinimumSize(QSize(0, 0))
        self.btn_code_editor.setMaximumSize(QSize(16777215, 40))
        self.btn_code_editor.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        icon2 = QIcon()
        icon2.addFile(u":/icons/icon--edit.svg", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.btn_code_editor.setIcon(icon2)
        self.btn_code_editor.setIconSize(QSize(24, 24))
        self.btn_code_editor.setFlat(False)

        self.horizontalLayout_3.addWidget(self.btn_code_editor)

        self.btn_sprite_editor = QPushButton(self.menu_frame)
        self.btn_sprite_editor.setObjectName(u"btn_sprite_editor")
        sizePolicy2.setHeightForWidth(self.btn_sprite_editor.sizePolicy().hasHeightForWidth())
        self.btn_sprite_editor.setSizePolicy(sizePolicy2)
        self.btn_sprite_editor.setMinimumSize(QSize(0, 0))
        self.btn_sprite_editor.setMaximumSize(QSize(16777215, 40))
        self.btn_sprite_editor.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        icon3 = QIcon()
        icon3.addFile(u":/icons/addons.svg", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.btn_sprite_editor.setIcon(icon3)
        self.btn_sprite_editor.setIconSize(QSize(20, 20))
        self.btn_sprite_editor.setFlat(False)

        self.horizontalLayout_3.addWidget(self.btn_sprite_editor)

        self.btn_map_editor = QPushButton(self.menu_frame)
        self.btn_map_editor.setObjectName(u"btn_map_editor")
        sizePolicy2.setHeightForWidth(self.btn_map_editor.sizePolicy().hasHeightForWidth())
        self.btn_map_editor.setSizePolicy(sizePolicy2)
        self.btn_map_editor.setMinimumSize(QSize(0, 0))
        self.btn_map_editor.setMaximumSize(QSize(16777215, 40))
        self.btn_map_editor.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        icon4 = QIcon()
        icon4.addFile(u":/icons/icon--settings.svg", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.btn_map_editor.setIcon(icon4)
        self.btn_map_editor.setIconSize(QSize(22, 22))
        self.btn_map_editor.setFlat(False)

        self.horizontalLayout_3.addWidget(self.btn_map_editor)

        self.btn_save = QPushButton(self.menu_frame)
        self.btn_save.setObjectName(u"btn_save")
        sizePolicy2.setHeightForWidth(self.btn_save.sizePolicy().hasHeightForWidth())
        self.btn_save.setSizePolicy(sizePolicy2)
        self.btn_save.setMinimumSize(QSize(0, 0))
        self.btn_save.setMaximumSize(QSize(80, 40))
        self.btn_save.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        icon5 = QIcon()
        icon5.addFile(u":/icons/\u4fdd\u5b58.svg", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.btn_save.setIcon(icon5)
        self.btn_save.setIconSize(QSize(16, 16))
        self.btn_save.setFlat(False)

        self.horizontalLayout_3.addWidget(self.btn_save)

        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_3.addItem(self.horizontalSpacer_2)

        self.btn_help = QPushButton(self.menu_frame)
        self.btn_help.setObjectName(u"btn_help")
        icon6 = QIcon()
        icon6.addFile(u":/icons/help.svg", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.btn_help.setIcon(icon6)
        self.btn_help.setIconSize(QSize(24, 24))

        self.horizontalLayout_3.addWidget(self.btn_help)

        self.horizontalLayout_3.setStretch(0, 1)
        self.horizontalLayout_3.setStretch(1, 1)
        self.horizontalLayout_3.setStretch(2, 1)
        self.horizontalLayout_3.setStretch(3, 1)
        self.horizontalLayout_3.setStretch(4, 1)
        self.horizontalLayout_3.setStretch(5, 1)
        self.horizontalLayout_3.setStretch(6, 6)

        self.verticalLayout_19.addWidget(self.menu_frame)

        self.editor_stacked = QStackedWidget(self.edit_stage_frame)
        self.editor_stacked.setObjectName(u"editor_stacked")
        self.editor_code_web = QWidget()
        self.editor_code_web.setObjectName(u"editor_code_web")
        self.verticalLayout_5 = QVBoxLayout(self.editor_code_web)
        self.verticalLayout_5.setSpacing(0)
        self.verticalLayout_5.setObjectName(u"verticalLayout_5")
        self.verticalLayout_5.setContentsMargins(0, 0, 0, 0)
        self.frame = QFrame(self.editor_code_web)
        self.frame.setObjectName(u"frame")
        self.frame.setFrameShape(QFrame.Shape.NoFrame)
        self.frame.setFrameShadow(QFrame.Shadow.Raised)
        self.frame.setLineWidth(0)
        self.horizontalLayout_2 = QHBoxLayout(self.frame)
        self.horizontalLayout_2.setSpacing(0)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.sidebar_frame = QFrame(self.frame)
        self.sidebar_frame.setObjectName(u"sidebar_frame")
        sizePolicy.setHeightForWidth(self.sidebar_frame.sizePolicy().hasHeightForWidth())
        self.sidebar_frame.setSizePolicy(sizePolicy)
        self.sidebar_frame.setMinimumSize(QSize(340, 0))
        self.sidebar_frame.setMaximumSize(QSize(340, 16777215))
        self.sidebar_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.sidebar_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.verticalLayout_2 = QVBoxLayout(self.sidebar_frame)
        self.verticalLayout_2.setSpacing(0)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(8, 0, 0, 0)
        self.screen_btn_frame = QFrame(self.sidebar_frame)
        self.screen_btn_frame.setObjectName(u"screen_btn_frame")
        sizePolicy3 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.screen_btn_frame.sizePolicy().hasHeightForWidth())
        self.screen_btn_frame.setSizePolicy(sizePolicy3)
        self.screen_btn_frame.setMinimumSize(QSize(324, 0))
        self.screen_btn_frame.setMaximumSize(QSize(324, 30))
        self.screen_btn_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.screen_btn_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.horizontalLayout_5 = QHBoxLayout(self.screen_btn_frame)
        self.horizontalLayout_5.setSpacing(5)
        self.horizontalLayout_5.setObjectName(u"horizontalLayout_5")
        self.horizontalLayout_5.setContentsMargins(5, 0, 5, 0)
        self.btn_run = QPushButton(self.screen_btn_frame)
        self.btn_run.setObjectName(u"btn_run")
        self.btn_run.setMinimumSize(QSize(24, 24))
        self.btn_run.setMaximumSize(QSize(24, 24))
        icon7 = QIcon()
        icon7.addFile(u":/icons/icon--play.svg", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.btn_run.setIcon(icon7)
        self.btn_run.setCheckable(True)

        self.horizontalLayout_5.addWidget(self.btn_run)

        self.btn_stop = QPushButton(self.screen_btn_frame)
        self.btn_stop.setObjectName(u"btn_stop")
        self.btn_stop.setMinimumSize(QSize(24, 24))
        self.btn_stop.setMaximumSize(QSize(24, 24))
        icon8 = QIcon()
        icon8.addFile(u":/icons/icon--stop-all.svg", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.btn_stop.setIcon(icon8)
        self.btn_stop.setCheckable(False)
        self.btn_stop.setAutoExclusive(True)

        self.horizontalLayout_5.addWidget(self.btn_stop)

        self.horizontalSpacer_3 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_5.addItem(self.horizontalSpacer_3)

        self.btn_full_screen = QPushButton(self.screen_btn_frame)
        self.btn_full_screen.setObjectName(u"btn_full_screen")
        self.btn_full_screen.setMinimumSize(QSize(24, 24))
        self.btn_full_screen.setMaximumSize(QSize(24, 24))
        icon9 = QIcon()
        icon9.addFile(u":/icons/icon--fullscreen.svg", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.btn_full_screen.setIcon(icon9)
        self.btn_full_screen.setIconSize(QSize(20, 20))
        self.btn_full_screen.setAutoExclusive(False)

        self.horizontalLayout_5.addWidget(self.btn_full_screen)

        self.horizontalLayout_5.setStretch(0, 1)
        self.horizontalLayout_5.setStretch(1, 1)
        self.horizontalLayout_5.setStretch(2, 4)
        self.horizontalLayout_5.setStretch(3, 1)

        self.verticalLayout_2.addWidget(self.screen_btn_frame)

        self.edit_stage_container = QFrame(self.sidebar_frame)
        self.edit_stage_container.setObjectName(u"edit_stage_container")
        sizePolicy.setHeightForWidth(self.edit_stage_container.sizePolicy().hasHeightForWidth())
        self.edit_stage_container.setSizePolicy(sizePolicy)
        self.edit_stage_container.setMinimumSize(QSize(324, 244))
        self.edit_stage_container.setMaximumSize(QSize(324, 244))
        self.edit_stage_container.setFrameShape(QFrame.Shape.StyledPanel)
        self.edit_stage_container.setFrameShadow(QFrame.Shadow.Raised)
        self.verticalLayout_10 = QVBoxLayout(self.edit_stage_container)
        self.verticalLayout_10.setSpacing(0)
        self.verticalLayout_10.setObjectName(u"verticalLayout_10")
        self.verticalLayout_10.setContentsMargins(0, 0, 0, 0)
        self.game_view = QGraphicsView(self.edit_stage_container)
        self.game_view.setObjectName(u"game_view")
        sizePolicy.setHeightForWidth(self.game_view.sizePolicy().hasHeightForWidth())
        self.game_view.setSizePolicy(sizePolicy)
        self.game_view.setMinimumSize(QSize(320, 240))
        self.game_view.setMaximumSize(QSize(320, 240))
        self.game_view.setStyleSheet(u"")
        self.game_view.setFrameShape(QFrame.Shape.Panel)
        self.game_view.setFrameShadow(QFrame.Shadow.Plain)
        self.game_view.setLineWidth(0)
        brush = QBrush(QColor(0, 0, 0, 255))
        brush.setStyle(Qt.BrushStyle.NoBrush)
        self.game_view.setBackgroundBrush(brush)
        brush1 = QBrush(QColor(0, 0, 0, 255))
        brush1.setStyle(Qt.BrushStyle.NoBrush)
        self.game_view.setForegroundBrush(brush1)

        self.verticalLayout_10.addWidget(self.game_view)


        self.verticalLayout_2.addWidget(self.edit_stage_container)

        self.outline_menu_frame = QFrame(self.sidebar_frame)
        self.outline_menu_frame.setObjectName(u"outline_menu_frame")
        sizePolicy4 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        sizePolicy4.setHorizontalStretch(0)
        sizePolicy4.setVerticalStretch(0)
        sizePolicy4.setHeightForWidth(self.outline_menu_frame.sizePolicy().hasHeightForWidth())
        self.outline_menu_frame.setSizePolicy(sizePolicy4)
        self.outline_menu_frame.setMinimumSize(QSize(324, 50))
        self.outline_menu_frame.setMaximumSize(QSize(324, 16777215))
        self.outline_menu_frame.setStyleSheet(u"")
        self.horizontalLayout_4 = QHBoxLayout(self.outline_menu_frame)
        self.horizontalLayout_4.setSpacing(0)
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.horizontalLayout_4.setContentsMargins(0, 0, 0, 0)
        self.btn_outline_sprite = QPushButton(self.outline_menu_frame)
        self.btn_outline_sprite.setObjectName(u"btn_outline_sprite")
        self.btn_outline_sprite.setCheckable(True)
        self.btn_outline_sprite.setChecked(True)
        self.btn_outline_sprite.setAutoExclusive(True)
        self.btn_outline_sprite.setAutoDefault(False)
        self.btn_outline_sprite.setFlat(False)

        self.horizontalLayout_4.addWidget(self.btn_outline_sprite)

        self.btn_outline_bg = QPushButton(self.outline_menu_frame)
        self.btn_outline_bg.setObjectName(u"btn_outline_bg")
        self.btn_outline_bg.setCheckable(True)
        self.btn_outline_bg.setAutoExclusive(True)

        self.horizontalLayout_4.addWidget(self.btn_outline_bg)

        self.btn_outline_sound = QPushButton(self.outline_menu_frame)
        self.btn_outline_sound.setObjectName(u"btn_outline_sound")
        self.btn_outline_sound.setCheckable(True)
        self.btn_outline_sound.setAutoExclusive(True)
        self.btn_outline_sound.setAutoDefault(False)
        self.btn_outline_sound.setFlat(False)

        self.horizontalLayout_4.addWidget(self.btn_outline_sound)

        self.btn_outline_code = QPushButton(self.outline_menu_frame)
        self.btn_outline_code.setObjectName(u"btn_outline_code")
        self.btn_outline_code.setCheckable(True)
        self.btn_outline_code.setChecked(False)
        self.btn_outline_code.setAutoExclusive(True)
        self.btn_outline_code.setAutoDefault(False)
        self.btn_outline_code.setFlat(False)

        self.horizontalLayout_4.addWidget(self.btn_outline_code)


        self.verticalLayout_2.addWidget(self.outline_menu_frame)

        self.outline_frame = QFrame(self.sidebar_frame)
        self.outline_frame.setObjectName(u"outline_frame")
        self.outline_frame.setMinimumSize(QSize(324, 0))
        self.outline_frame.setMaximumSize(QSize(324, 16777215))
        self.outline_frame.setStyleSheet(u"")
        self.outline_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.outline_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.verticalLayout_6 = QVBoxLayout(self.outline_frame)
        self.verticalLayout_6.setSpacing(0)
        self.verticalLayout_6.setObjectName(u"verticalLayout_6")
        self.verticalLayout_6.setContentsMargins(0, 0, 0, 0)
        self.outline_stracked = QStackedWidget(self.outline_frame)
        self.outline_stracked.setObjectName(u"outline_stracked")
        self.outline_stracked.setMinimumSize(QSize(324, 0))
        self.outline_stracked.setMaximumSize(QSize(324, 16777215))
        self.outline_stracked.setStyleSheet(u"")
        self.page_sprite = QWidget()
        self.page_sprite.setObjectName(u"page_sprite")
        self.verticalLayout_12 = QVBoxLayout(self.page_sprite)
        self.verticalLayout_12.setObjectName(u"verticalLayout_12")
        self.verticalLayout_12.setContentsMargins(0, 0, 0, 0)
        self.sprite_page_frame = QFrame(self.page_sprite)
        self.sprite_page_frame.setObjectName(u"sprite_page_frame")
        self.sprite_page_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.sprite_page_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.verticalLayout_15 = QVBoxLayout(self.sprite_page_frame)
        self.verticalLayout_15.setSpacing(0)
        self.verticalLayout_15.setObjectName(u"verticalLayout_15")
        self.verticalLayout_15.setContentsMargins(0, 0, 0, 0)
        self.list_sprite = QListWidget(self.sprite_page_frame)
        self.list_sprite.setObjectName(u"list_sprite")
        self.list_sprite.setIconSize(QSize(80, 80))
        self.list_sprite.setMovement(QListView.Movement.Static)
        self.list_sprite.setResizeMode(QListView.ResizeMode.Adjust)
        self.list_sprite.setSpacing(10)
        self.list_sprite.setViewMode(QListView.ViewMode.IconMode)

        self.verticalLayout_15.addWidget(self.list_sprite)


        self.verticalLayout_12.addWidget(self.sprite_page_frame)

        self.outline_stracked.addWidget(self.page_sprite)
        self.page_map = QWidget()
        self.page_map.setObjectName(u"page_map")
        self.verticalLayout_13 = QVBoxLayout(self.page_map)
        self.verticalLayout_13.setObjectName(u"verticalLayout_13")
        self.verticalLayout_13.setContentsMargins(0, 0, 0, 0)
        self.map_page_frame = QFrame(self.page_map)
        self.map_page_frame.setObjectName(u"map_page_frame")
        self.map_page_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.map_page_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.verticalLayout_21 = QVBoxLayout(self.map_page_frame)
        self.verticalLayout_21.setObjectName(u"verticalLayout_21")
        self.verticalLayout_21.setContentsMargins(0, 0, 0, 0)
        self.list_map = QListWidget(self.map_page_frame)
        self.list_map.setObjectName(u"list_map")

        self.verticalLayout_21.addWidget(self.list_map)


        self.verticalLayout_13.addWidget(self.map_page_frame)

        self.outline_stracked.addWidget(self.page_map)
        self.page_sound = QWidget()
        self.page_sound.setObjectName(u"page_sound")
        self.verticalLayout_14 = QVBoxLayout(self.page_sound)
        self.verticalLayout_14.setObjectName(u"verticalLayout_14")
        self.sound_page_frame = QFrame(self.page_sound)
        self.sound_page_frame.setObjectName(u"sound_page_frame")
        self.sound_page_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.sound_page_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.label_4 = QLabel(self.sound_page_frame)
        self.label_4.setObjectName(u"label_4")
        self.label_4.setGeometry(QRect(40, 30, 58, 16))
        self.listWidget = QListWidget(self.sound_page_frame)
        self.listWidget.setObjectName(u"listWidget")
        self.listWidget.setGeometry(QRect(80, 90, 256, 192))

        self.verticalLayout_14.addWidget(self.sound_page_frame)

        self.outline_stracked.addWidget(self.page_sound)
        self.page_code = QWidget()
        self.page_code.setObjectName(u"page_code")
        self.verticalLayout_9 = QVBoxLayout(self.page_code)
        self.verticalLayout_9.setObjectName(u"verticalLayout_9")
        self.verticalLayout_9.setContentsMargins(0, 0, 0, 0)
        self.code_page_frame = QFrame(self.page_code)
        self.code_page_frame.setObjectName(u"code_page_frame")
        self.code_page_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.code_page_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.verticalLayout_16 = QVBoxLayout(self.code_page_frame)
        self.verticalLayout_16.setObjectName(u"verticalLayout_16")
        self.verticalLayout_16.setContentsMargins(4, 4, 4, 4)
        self.list_code = QListWidget(self.code_page_frame)
        self.list_code.setObjectName(u"list_code")

        self.verticalLayout_16.addWidget(self.list_code)


        self.verticalLayout_9.addWidget(self.code_page_frame)

        self.outline_stracked.addWidget(self.page_code)

        self.verticalLayout_6.addWidget(self.outline_stracked)


        self.verticalLayout_2.addWidget(self.outline_frame)


        self.horizontalLayout_2.addWidget(self.sidebar_frame)

        self.editor_frame = QFrame(self.frame)
        self.editor_frame.setObjectName(u"editor_frame")
        sizePolicy5 = QSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        sizePolicy5.setHorizontalStretch(0)
        sizePolicy5.setVerticalStretch(0)
        sizePolicy5.setHeightForWidth(self.editor_frame.sizePolicy().hasHeightForWidth())
        self.editor_frame.setSizePolicy(sizePolicy5)
        self.editor_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.editor_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.verticalLayout_3 = QVBoxLayout(self.editor_frame)
        self.verticalLayout_3.setSpacing(0)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.verticalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.toolbar_frame = QFrame(self.editor_frame)
        self.toolbar_frame.setObjectName(u"toolbar_frame")
        sizePolicy3.setHeightForWidth(self.toolbar_frame.sizePolicy().hasHeightForWidth())
        self.toolbar_frame.setSizePolicy(sizePolicy3)
        self.toolbar_frame.setMinimumSize(QSize(0, 30))
        self.toolbar_frame.setMaximumSize(QSize(16777215, 30))
        self.toolbar_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.toolbar_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.horizontalLayout = QHBoxLayout(self.toolbar_frame)
        self.horizontalLayout.setSpacing(0)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.tab_frame = QFrame(self.toolbar_frame)
        self.tab_frame.setObjectName(u"tab_frame")
        sizePolicy3.setHeightForWidth(self.tab_frame.sizePolicy().hasHeightForWidth())
        self.tab_frame.setSizePolicy(sizePolicy3)
        self.tab_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.tab_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.tab_frame.setLineWidth(0)
        self.horizontalLayout_6 = QHBoxLayout(self.tab_frame)
        self.horizontalLayout_6.setSpacing(0)
        self.horizontalLayout_6.setObjectName(u"horizontalLayout_6")
        self.horizontalLayout_6.setContentsMargins(0, 0, 0, 0)
        self.tab = QFrame(self.tab_frame)
        self.tab.setObjectName(u"tab")
        sizePolicy6 = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        sizePolicy6.setHorizontalStretch(0)
        sizePolicy6.setVerticalStretch(0)
        sizePolicy6.setHeightForWidth(self.tab.sizePolicy().hasHeightForWidth())
        self.tab.setSizePolicy(sizePolicy6)
        self.tab.setMinimumSize(QSize(0, 30))
        self.tab.setStyleSheet(u"")
        self.tab.setFrameShape(QFrame.Shape.NoFrame)
        self.tab.setFrameShadow(QFrame.Shadow.Raised)
        self.tab.setLineWidth(0)
        self.horizontalLayout_7 = QHBoxLayout(self.tab)
        self.horizontalLayout_7.setSpacing(0)
        self.horizontalLayout_7.setObjectName(u"horizontalLayout_7")
        self.horizontalLayout_7.setContentsMargins(0, 0, 0, 0)

        self.horizontalLayout_6.addWidget(self.tab, 0, Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)

        self.btn_add_tab = QPushButton(self.tab_frame)
        self.btn_add_tab.setObjectName(u"btn_add_tab")
        sizePolicy7 = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        sizePolicy7.setHorizontalStretch(0)
        sizePolicy7.setVerticalStretch(0)
        sizePolicy7.setHeightForWidth(self.btn_add_tab.sizePolicy().hasHeightForWidth())
        self.btn_add_tab.setSizePolicy(sizePolicy7)
        self.btn_add_tab.setMinimumSize(QSize(24, 24))
        self.btn_add_tab.setMaximumSize(QSize(24, 24))
        self.btn_add_tab.setFlat(True)

        self.horizontalLayout_6.addWidget(self.btn_add_tab)


        self.horizontalLayout.addWidget(self.tab_frame, 0, Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignBottom)

        self.horizontalLayout.setStretch(0, 1)

        self.verticalLayout_3.addWidget(self.toolbar_frame)

        self.code_frame = QFrame(self.editor_frame)
        self.code_frame.setObjectName(u"code_frame")
        sizePolicy8 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy8.setHorizontalStretch(0)
        sizePolicy8.setVerticalStretch(0)
        sizePolicy8.setHeightForWidth(self.code_frame.sizePolicy().hasHeightForWidth())
        self.code_frame.setSizePolicy(sizePolicy8)
        self.code_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.code_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.verticalLayout = QVBoxLayout(self.code_frame)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(8, 0, 8, 0)
        self.splitter = QSplitter(self.code_frame)
        self.splitter.setObjectName(u"splitter")
        sizePolicy8.setHeightForWidth(self.splitter.sizePolicy().hasHeightForWidth())
        self.splitter.setSizePolicy(sizePolicy8)
        self.splitter.setOrientation(Qt.Orientation.Vertical)
        self.code_stacked = QStackedWidget(self.splitter)
        self.code_stacked.setObjectName(u"code_stacked")
        sizePolicy8.setHeightForWidth(self.code_stacked.sizePolicy().hasHeightForWidth())
        self.code_stacked.setSizePolicy(sizePolicy8)
        self.code_stacked.setMinimumSize(QSize(0, 0))
        self.splitter.addWidget(self.code_stacked)
        self.console_output = QPlainTextEdit(self.splitter)
        self.console_output.setObjectName(u"console_output")
        self.console_output.setMaximumSize(QSize(16777215, 16777215))
        self.console_output.setFrameShape(QFrame.Shape.Box)
        self.splitter.addWidget(self.console_output)

        self.verticalLayout.addWidget(self.splitter)


        self.verticalLayout_3.addWidget(self.code_frame)


        self.horizontalLayout_2.addWidget(self.editor_frame)


        self.verticalLayout_5.addWidget(self.frame)

        self.editor_stacked.addWidget(self.editor_code_web)
        self.editor_sprite_web = QWidget()
        self.editor_sprite_web.setObjectName(u"editor_sprite_web")
        self.verticalLayout_18 = QVBoxLayout(self.editor_sprite_web)
        self.verticalLayout_18.setSpacing(0)
        self.verticalLayout_18.setObjectName(u"verticalLayout_18")
        self.verticalLayout_18.setContentsMargins(0, 0, 0, 0)
        self.widget_2 = QWidget(self.editor_sprite_web)
        self.widget_2.setObjectName(u"widget_2")
        self.horizontalLayout_11 = QHBoxLayout(self.widget_2)
        self.horizontalLayout_11.setSpacing(0)
        self.horizontalLayout_11.setObjectName(u"horizontalLayout_11")
        self.horizontalLayout_11.setContentsMargins(0, 0, 0, 0)
        self.sprite_fps_list = QListWidget(self.widget_2)
        self.sprite_fps_list.setObjectName(u"sprite_fps_list")
        self.sprite_fps_list.setMinimumSize(QSize(100, 0))
        self.sprite_fps_list.setMaximumSize(QSize(100, 16777215))
        self.sprite_fps_list.setStyleSheet(u"")
        self.sprite_fps_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sprite_fps_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sprite_fps_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.sprite_fps_list.setMovement(QListView.Movement.Static)
        self.sprite_fps_list.setResizeMode(QListView.ResizeMode.Adjust)
        self.sprite_fps_list.setSpacing(5)
        self.sprite_fps_list.setViewMode(QListView.ViewMode.IconMode)

        self.horizontalLayout_11.addWidget(self.sprite_fps_list)

        self.sprite_canvas = QGraphicsView(self.widget_2)
        self.sprite_canvas.setObjectName(u"sprite_canvas")
        self.sprite_canvas.setStyleSheet(u"")
        self.sprite_canvas.setFrameShape(QFrame.Shape.NoFrame)
        self.sprite_canvas.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sprite_canvas.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.horizontalLayout_11.addWidget(self.sprite_canvas)

        self.editor_preview_panel = QWidget(self.widget_2)
        self.editor_preview_panel.setObjectName(u"editor_preview_panel")
        self.editor_preview_panel.setMinimumSize(QSize(264, 0))
        self.editor_preview_panel.setMaximumSize(QSize(264, 16777215))
        self.verticalLayout_20 = QVBoxLayout(self.editor_preview_panel)
        self.verticalLayout_20.setSpacing(1)
        self.verticalLayout_20.setObjectName(u"verticalLayout_20")
        self.verticalLayout_20.setContentsMargins(0, 0, 0, 0)
        self.animate_label = QLabel(self.editor_preview_panel)
        self.animate_label.setObjectName(u"animate_label")
        self.animate_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.verticalLayout_20.addWidget(self.animate_label)

        self.preview_bg = QFrame(self.editor_preview_panel)
        self.preview_bg.setObjectName(u"preview_bg")
        self.preview_bg.setMinimumSize(QSize(256, 256))
        self.preview_bg.setMaximumSize(QSize(256, 256))
        self.preview_bg.setFrameShape(QFrame.Shape.NoFrame)
        self.preview_bg.setFrameShadow(QFrame.Shadow.Raised)
        self.verticalLayout_17 = QVBoxLayout(self.preview_bg)
        self.verticalLayout_17.setSpacing(0)
        self.verticalLayout_17.setObjectName(u"verticalLayout_17")
        self.verticalLayout_17.setContentsMargins(0, 0, 0, 0)
        self.animate_preview = QLabel(self.preview_bg)
        self.animate_preview.setObjectName(u"animate_preview")
        self.animate_preview.setMinimumSize(QSize(256, 256))
        self.animate_preview.setMaximumSize(QSize(256, 256))
        self.animate_preview.setStyleSheet(u"")
        self.animate_preview.setFrameShape(QFrame.Shape.StyledPanel)
        self.animate_preview.setScaledContents(False)
        self.animate_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.verticalLayout_17.addWidget(self.animate_preview, 0, Qt.AlignmentFlag.AlignHCenter|Qt.AlignmentFlag.AlignTop)

        self.fps_slider_box = QHBoxLayout()
        self.fps_slider_box.setObjectName(u"fps_slider_box")
        self.fps_slider_box.setContentsMargins(-1, -1, -1, 4)
        self.horizontalSpacer_6 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.fps_slider_box.addItem(self.horizontalSpacer_6)

        self.fps_slider = QSlider(self.preview_bg)
        self.fps_slider.setObjectName(u"fps_slider")
        self.fps_slider.setStyleSheet(u"")
        self.fps_slider.setOrientation(Qt.Orientation.Horizontal)

        self.fps_slider_box.addWidget(self.fps_slider)

        self.horizontalSpacer_7 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.fps_slider_box.addItem(self.horizontalSpacer_7)

        self.fps_slider_box.setStretch(0, 1)
        self.fps_slider_box.setStretch(1, 2)
        self.fps_slider_box.setStretch(2, 1)

        self.verticalLayout_17.addLayout(self.fps_slider_box)


        self.verticalLayout_20.addWidget(self.preview_bg, 0, Qt.AlignmentFlag.AlignHCenter)

        self.btn_preview_btns = QFrame(self.editor_preview_panel)
        self.btn_preview_btns.setObjectName(u"btn_preview_btns")
        self.btn_preview_btns.setFrameShape(QFrame.Shape.StyledPanel)
        self.btn_preview_btns.setFrameShadow(QFrame.Shadow.Raised)
        self.horizontalLayout_8 = QHBoxLayout(self.btn_preview_btns)
        self.horizontalLayout_8.setSpacing(4)
        self.horizontalLayout_8.setObjectName(u"horizontalLayout_8")
        self.horizontalLayout_8.setContentsMargins(8, 8, 8, 8)
        self.btn_preview_prev = QPushButton(self.btn_preview_btns)
        self.btn_preview_prev.setObjectName(u"btn_preview_prev")
        self.btn_preview_prev.setMinimumSize(QSize(38, 24))
        self.btn_preview_prev.setMaximumSize(QSize(38, 24))
        icon10 = QIcon()
        icon10.addFile(u":/icons/btn_preview_prev.svg", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.btn_preview_prev.setIcon(icon10)
        self.btn_preview_prev.setIconSize(QSize(28, 16))
        self.btn_preview_prev.setFlat(True)

        self.horizontalLayout_8.addWidget(self.btn_preview_prev)

        self.btn_preview_play = QPushButton(self.btn_preview_btns)
        self.btn_preview_play.setObjectName(u"btn_preview_play")
        self.btn_preview_play.setMinimumSize(QSize(38, 24))
        self.btn_preview_play.setMaximumSize(QSize(38, 24))
        icon11 = QIcon()
        icon11.addFile(u":/icons/btn_preview_play.svg", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        icon11.addFile(u":/icons/btn_preview_pause.svg", QSize(), QIcon.Mode.Normal, QIcon.State.On)
        self.btn_preview_play.setIcon(icon11)
        self.btn_preview_play.setIconSize(QSize(28, 16))
        self.btn_preview_play.setCheckable(True)
        self.btn_preview_play.setFlat(True)

        self.horizontalLayout_8.addWidget(self.btn_preview_play)

        self.btn_preview_next = QPushButton(self.btn_preview_btns)
        self.btn_preview_next.setObjectName(u"btn_preview_next")
        self.btn_preview_next.setMinimumSize(QSize(38, 24))
        self.btn_preview_next.setMaximumSize(QSize(38, 24))
        icon12 = QIcon()
        icon12.addFile(u":/icons/btn_preview_next.svg", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.btn_preview_next.setIcon(icon12)
        self.btn_preview_next.setIconSize(QSize(28, 16))
        self.btn_preview_next.setFlat(True)

        self.horizontalLayout_8.addWidget(self.btn_preview_next)

        self.btn_preview_scale = QPushButton(self.btn_preview_btns)
        self.btn_preview_scale.setObjectName(u"btn_preview_scale")
        self.btn_preview_scale.setMinimumSize(QSize(38, 24))
        self.btn_preview_scale.setMaximumSize(QSize(38, 24))
        icon13 = QIcon()
        icon13.addFile(u":/icons/btn_preview_scale.svg", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.btn_preview_scale.setIcon(icon13)
        self.btn_preview_scale.setIconSize(QSize(28, 16))
        self.btn_preview_scale.setFlat(True)

        self.horizontalLayout_8.addWidget(self.btn_preview_scale)

        self.btn_preview_change_bg = QPushButton(self.btn_preview_btns)
        self.btn_preview_change_bg.setObjectName(u"btn_preview_change_bg")
        self.btn_preview_change_bg.setMinimumSize(QSize(38, 24))
        self.btn_preview_change_bg.setMaximumSize(QSize(38, 24))
        icon14 = QIcon()
        icon14.addFile(u":/icons/btn_preview_change_bg.svg", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.btn_preview_change_bg.setIcon(icon14)
        self.btn_preview_change_bg.setIconSize(QSize(28, 16))
        self.btn_preview_change_bg.setFlat(True)

        self.horizontalLayout_8.addWidget(self.btn_preview_change_bg)

        self.btn_preview_add = QPushButton(self.btn_preview_btns)
        self.btn_preview_add.setObjectName(u"btn_preview_add")
        self.btn_preview_add.setMinimumSize(QSize(38, 24))
        self.btn_preview_add.setMaximumSize(QSize(38, 24))
        icon15 = QIcon()
        icon15.addFile(u":/icons/btn_preview_add.svg", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.btn_preview_add.setIcon(icon15)
        self.btn_preview_add.setIconSize(QSize(28, 16))
        self.btn_preview_add.setFlat(True)

        self.horizontalLayout_8.addWidget(self.btn_preview_add)


        self.verticalLayout_20.addWidget(self.btn_preview_btns, 0, Qt.AlignmentFlag.AlignHCenter)

        self.animate_list = QTreeWidget(self.editor_preview_panel)
        __qtreewidgetitem = QTreeWidgetItem()
        __qtreewidgetitem.setText(0, u"1");
        self.animate_list.setHeaderItem(__qtreewidgetitem)
        self.animate_list.setObjectName(u"animate_list")
        self.animate_list.setMinimumSize(QSize(256, 0))
        self.animate_list.setMaximumSize(QSize(256, 16777215))
        self.animate_list.setStyleSheet(u"")
        self.animate_list.setFrameShape(QFrame.Shape.NoFrame)
        self.animate_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.animate_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.animate_list.header().setVisible(False)

        self.verticalLayout_20.addWidget(self.animate_list, 0, Qt.AlignmentFlag.AlignHCenter)


        self.horizontalLayout_11.addWidget(self.editor_preview_panel)


        self.verticalLayout_18.addWidget(self.widget_2)

        self.editor_stacked.addWidget(self.editor_sprite_web)
        self.editor_map_web = QWidget()
        self.editor_map_web.setObjectName(u"editor_map_web")
        self.verticalLayout_29 = QVBoxLayout(self.editor_map_web)
        self.verticalLayout_29.setSpacing(0)
        self.verticalLayout_29.setObjectName(u"verticalLayout_29")
        self.verticalLayout_29.setContentsMargins(0, 0, 0, 0)
        self.editor_map_widget = QWidget(self.editor_map_web)
        self.editor_map_widget.setObjectName(u"editor_map_widget")
        self.horizontalLayout_24 = QHBoxLayout(self.editor_map_widget)
        self.horizontalLayout_24.setSpacing(0)
        self.horizontalLayout_24.setObjectName(u"horizontalLayout_24")
        self.horizontalLayout_24.setContentsMargins(0, 0, 0, 0)
        self.editor_map_left = QFrame(self.editor_map_widget)
        self.editor_map_left.setObjectName(u"editor_map_left")
        sizePolicy9 = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        sizePolicy9.setHorizontalStretch(0)
        sizePolicy9.setVerticalStretch(0)
        sizePolicy9.setHeightForWidth(self.editor_map_left.sizePolicy().hasHeightForWidth())
        self.editor_map_left.setSizePolicy(sizePolicy9)
        self.editor_map_left.setMinimumSize(QSize(265, 0))
        self.editor_map_left.setMaximumSize(QSize(265, 16777215))
        self.verticalLayout_24 = QVBoxLayout(self.editor_map_left)
        self.verticalLayout_24.setSpacing(0)
        self.verticalLayout_24.setObjectName(u"verticalLayout_24")
        self.verticalLayout_24.setContentsMargins(0, 0, 0, 0)
        self.editor_map_res_list = QFrame(self.editor_map_left)
        self.editor_map_res_list.setObjectName(u"editor_map_res_list")
        sizePolicy6.setHeightForWidth(self.editor_map_res_list.sizePolicy().hasHeightForWidth())
        self.editor_map_res_list.setSizePolicy(sizePolicy6)
        self.editor_map_res_list.setMinimumSize(QSize(265, 0))
        self.editor_map_res_list.setMaximumSize(QSize(265, 16777215))
        self.editor_map_res_list.setFrameShape(QFrame.Shape.NoFrame)
        self.editor_map_res_list.setFrameShadow(QFrame.Shadow.Raised)
        self.editor_map_res_list.setLineWidth(0)
        self.verticalLayout_26 = QVBoxLayout(self.editor_map_res_list)
        self.verticalLayout_26.setSpacing(0)
        self.verticalLayout_26.setObjectName(u"verticalLayout_26")
        self.verticalLayout_26.setContentsMargins(4, 0, 4, 0)
        self.res_list_toobar = QFrame(self.editor_map_res_list)
        self.res_list_toobar.setObjectName(u"res_list_toobar")
        sizePolicy9.setHeightForWidth(self.res_list_toobar.sizePolicy().hasHeightForWidth())
        self.res_list_toobar.setSizePolicy(sizePolicy9)
        self.res_list_toobar.setMinimumSize(QSize(256, 30))
        self.res_list_toobar.setMaximumSize(QSize(256, 30))
        self.res_list_toobar.setFrameShape(QFrame.Shape.StyledPanel)
        self.res_list_toobar.setFrameShadow(QFrame.Shadow.Raised)
        self.horizontalLayout_14 = QHBoxLayout(self.res_list_toobar)
        self.horizontalLayout_14.setSpacing(2)
        self.horizontalLayout_14.setObjectName(u"horizontalLayout_14")
        self.horizontalLayout_14.setContentsMargins(4, 0, 4, 0)
        self.btn_res_list_open = QPushButton(self.res_list_toobar)
        self.btn_res_list_open.setObjectName(u"btn_res_list_open")

        self.horizontalLayout_14.addWidget(self.btn_res_list_open)

        self.btn_res_list_upload = QPushButton(self.res_list_toobar)
        self.btn_res_list_upload.setObjectName(u"btn_res_list_upload")

        self.horizontalLayout_14.addWidget(self.btn_res_list_upload)

        self.btn_res_list_clear = QPushButton(self.res_list_toobar)
        self.btn_res_list_clear.setObjectName(u"btn_res_list_clear")

        self.horizontalLayout_14.addWidget(self.btn_res_list_clear)

        self.horizontalSpacer_13 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_14.addItem(self.horizontalSpacer_13)

        self.res_list_search = QLineEdit(self.res_list_toobar)
        self.res_list_search.setObjectName(u"res_list_search")

        self.horizontalLayout_14.addWidget(self.res_list_search)


        self.verticalLayout_26.addWidget(self.res_list_toobar)

        self.res_list_view = QGraphicsView(self.editor_map_res_list)
        self.res_list_view.setObjectName(u"res_list_view")
        sizePolicy10 = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        sizePolicy10.setHorizontalStretch(0)
        sizePolicy10.setVerticalStretch(0)
        sizePolicy10.setHeightForWidth(self.res_list_view.sizePolicy().hasHeightForWidth())
        self.res_list_view.setSizePolicy(sizePolicy10)
        self.res_list_view.setMinimumSize(QSize(256, 0))
        self.res_list_view.setMaximumSize(QSize(256, 16777215))
        self.res_list_view.setAutoFillBackground(True)
        self.res_list_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.res_list_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.verticalLayout_26.addWidget(self.res_list_view)

        self.res_col_toolbar = QFrame(self.editor_map_res_list)
        self.res_col_toolbar.setObjectName(u"res_col_toolbar")
        sizePolicy9.setHeightForWidth(self.res_col_toolbar.sizePolicy().hasHeightForWidth())
        self.res_col_toolbar.setSizePolicy(sizePolicy9)
        self.res_col_toolbar.setMinimumSize(QSize(256, 30))
        self.res_col_toolbar.setMaximumSize(QSize(256, 30))
        self.res_col_toolbar.setFrameShape(QFrame.Shape.StyledPanel)
        self.res_col_toolbar.setMidLineWidth(0)
        self.horizontalLayout_15 = QHBoxLayout(self.res_col_toolbar)
        self.horizontalLayout_15.setSpacing(0)
        self.horizontalLayout_15.setObjectName(u"horizontalLayout_15")
        self.horizontalLayout_15.setContentsMargins(0, 0, 0, 0)
        self.btn_res_col_move = QPushButton(self.res_col_toolbar)
        self.btn_res_col_move.setObjectName(u"btn_res_col_move")
        self.btn_res_col_move.setMinimumSize(QSize(0, 30))
        self.btn_res_col_move.setMaximumSize(QSize(16777215, 30))
        self.btn_res_col_move.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_res_col_move.setFlat(True)

        self.horizontalLayout_15.addWidget(self.btn_res_col_move)

        self.btn_res_col_add = QPushButton(self.res_col_toolbar)
        self.btn_res_col_add.setObjectName(u"btn_res_col_add")
        self.btn_res_col_add.setMinimumSize(QSize(0, 30))
        self.btn_res_col_add.setMaximumSize(QSize(16777215, 30))
        self.btn_res_col_add.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_res_col_add.setFlat(True)

        self.horizontalLayout_15.addWidget(self.btn_res_col_add)

        self.btn_res_col_del = QPushButton(self.res_col_toolbar)
        self.btn_res_col_del.setObjectName(u"btn_res_col_del")
        self.btn_res_col_del.setMinimumSize(QSize(0, 30))
        self.btn_res_col_del.setMaximumSize(QSize(16777215, 30))
        self.btn_res_col_del.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_res_col_del.setFlat(True)

        self.horizontalLayout_15.addWidget(self.btn_res_col_del)

        self.btn_res_col_reset = QPushButton(self.res_col_toolbar)
        self.btn_res_col_reset.setObjectName(u"btn_res_col_reset")
        self.btn_res_col_reset.setMinimumSize(QSize(0, 30))
        self.btn_res_col_reset.setMaximumSize(QSize(16777215, 30))
        self.btn_res_col_reset.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_res_col_reset.setFlat(True)

        self.horizontalLayout_15.addWidget(self.btn_res_col_reset)

        self.btn_res_col_snap = QPushButton(self.res_col_toolbar)
        self.btn_res_col_snap.setObjectName(u"btn_res_col_snap")
        self.btn_res_col_snap.setMinimumSize(QSize(0, 30))
        self.btn_res_col_snap.setMaximumSize(QSize(16777215, 30))
        self.btn_res_col_snap.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_res_col_snap.setCheckable(True)
        self.btn_res_col_snap.setChecked(True)
        self.btn_res_col_snap.setFlat(True)

        self.horizontalLayout_15.addWidget(self.btn_res_col_snap)


        self.verticalLayout_26.addWidget(self.res_col_toolbar)

        self.widget = QWidget(self.editor_map_res_list)
        self.widget.setObjectName(u"widget")
        self.verticalLayout_22 = QVBoxLayout(self.widget)
        self.verticalLayout_22.setSpacing(0)
        self.verticalLayout_22.setObjectName(u"verticalLayout_22")
        self.verticalLayout_22.setContentsMargins(0, 0, 0, 0)
        self.col_editor_view = QGraphicsView(self.widget)
        self.col_editor_view.setObjectName(u"col_editor_view")
        sizePolicy9.setHeightForWidth(self.col_editor_view.sizePolicy().hasHeightForWidth())
        self.col_editor_view.setSizePolicy(sizePolicy9)
        self.col_editor_view.setMinimumSize(QSize(256, 256))
        self.col_editor_view.setMaximumSize(QSize(240, 240))
        self.col_editor_view.setAutoFillBackground(True)
        self.col_editor_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.col_editor_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.verticalLayout_22.addWidget(self.col_editor_view, 0, Qt.AlignmentFlag.AlignTop)

        self.res_info = QWidget(self.widget)
        self.res_info.setObjectName(u"res_info")
        sizePolicy9.setHeightForWidth(self.res_info.sizePolicy().hasHeightForWidth())
        self.res_info.setSizePolicy(sizePolicy9)
        self.res_info.setMinimumSize(QSize(256, 30))
        self.res_info.setMaximumSize(QSize(256, 30))
        self.horizontalLayout_23 = QHBoxLayout(self.res_info)
        self.horizontalLayout_23.setObjectName(u"horizontalLayout_23")
        self.horizontalLayout_23.setContentsMargins(0, 0, 0, 0)
        self.horizontalSpacer_11 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_23.addItem(self.horizontalSpacer_11)

        self.label_res_list_name = QLabel(self.res_info)
        self.label_res_list_name.setObjectName(u"label_res_list_name")

        self.horizontalLayout_23.addWidget(self.label_res_list_name)

        self.label_res_list_id = QLabel(self.res_info)
        self.label_res_list_id.setObjectName(u"label_res_list_id")

        self.horizontalLayout_23.addWidget(self.label_res_list_id)

        self.label_res_list_size = QLabel(self.res_info)
        self.label_res_list_size.setObjectName(u"label_res_list_size")

        self.horizontalLayout_23.addWidget(self.label_res_list_size)

        self.horizontalSpacer_9 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_23.addItem(self.horizontalSpacer_9)


        self.verticalLayout_22.addWidget(self.res_info)


        self.verticalLayout_26.addWidget(self.widget)


        self.verticalLayout_24.addWidget(self.editor_map_res_list)

        self.verticalLayout_24.setStretch(0, 1)

        self.horizontalLayout_24.addWidget(self.editor_map_left)

        self.editor_map_mid = QWidget(self.editor_map_widget)
        self.editor_map_mid.setObjectName(u"editor_map_mid")
        sizePolicy11 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sizePolicy11.setHorizontalStretch(0)
        sizePolicy11.setVerticalStretch(0)
        sizePolicy11.setHeightForWidth(self.editor_map_mid.sizePolicy().hasHeightForWidth())
        self.editor_map_mid.setSizePolicy(sizePolicy11)
        self.verticalLayout_25 = QVBoxLayout(self.editor_map_mid)
        self.verticalLayout_25.setSpacing(0)
        self.verticalLayout_25.setObjectName(u"verticalLayout_25")
        self.verticalLayout_25.setContentsMargins(0, 0, 0, 0)
        self.editor_map_toolbar = QFrame(self.editor_map_mid)
        self.editor_map_toolbar.setObjectName(u"editor_map_toolbar")
        sizePolicy11.setHeightForWidth(self.editor_map_toolbar.sizePolicy().hasHeightForWidth())
        self.editor_map_toolbar.setSizePolicy(sizePolicy11)
        self.editor_map_toolbar.setMinimumSize(QSize(0, 30))
        self.editor_map_toolbar.setMaximumSize(QSize(16777215, 30))
        self.editor_map_toolbar.setFrameShape(QFrame.Shape.StyledPanel)
        self.editor_map_toolbar.setFrameShadow(QFrame.Shadow.Raised)
        self.horizontalLayout_18 = QHBoxLayout(self.editor_map_toolbar)
        self.horizontalLayout_18.setSpacing(1)
        self.horizontalLayout_18.setObjectName(u"horizontalLayout_18")
        self.horizontalLayout_18.setContentsMargins(0, 0, 0, 0)
        self.btn_editor_map_new = QPushButton(self.editor_map_toolbar)
        self.btn_editor_map_new.setObjectName(u"btn_editor_map_new")

        self.horizontalLayout_18.addWidget(self.btn_editor_map_new)

        self.btn_editor_map_import = QPushButton(self.editor_map_toolbar)
        self.btn_editor_map_import.setObjectName(u"btn_editor_map_import")

        self.horizontalLayout_18.addWidget(self.btn_editor_map_import)

        self.btn_editor_map_export = QPushButton(self.editor_map_toolbar)
        self.btn_editor_map_export.setObjectName(u"btn_editor_map_export")

        self.horizontalLayout_18.addWidget(self.btn_editor_map_export)

        self.btn_editor_map_move = QPushButton(self.editor_map_toolbar)
        self.buttonGroup = QButtonGroup(Form)
        self.buttonGroup.setObjectName(u"buttonGroup")
        self.buttonGroup.addButton(self.btn_editor_map_move)
        self.btn_editor_map_move.setObjectName(u"btn_editor_map_move")
        self.btn_editor_map_move.setCheckable(True)
        self.btn_editor_map_move.setChecked(True)

        self.horizontalLayout_18.addWidget(self.btn_editor_map_move)

        self.btn_editor_map_draw = QPushButton(self.editor_map_toolbar)
        self.buttonGroup.addButton(self.btn_editor_map_draw)
        self.btn_editor_map_draw.setObjectName(u"btn_editor_map_draw")
        self.btn_editor_map_draw.setCheckable(True)

        self.horizontalLayout_18.addWidget(self.btn_editor_map_draw)

        self.btn_editor_map_erase = QPushButton(self.editor_map_toolbar)
        self.buttonGroup.addButton(self.btn_editor_map_erase)
        self.btn_editor_map_erase.setObjectName(u"btn_editor_map_erase")
        self.btn_editor_map_erase.setCheckable(True)

        self.horizontalLayout_18.addWidget(self.btn_editor_map_erase)

        self.btn_editor_map_select = QPushButton(self.editor_map_toolbar)
        self.buttonGroup.addButton(self.btn_editor_map_select)
        self.btn_editor_map_select.setObjectName(u"btn_editor_map_select")
        self.btn_editor_map_select.setCheckable(True)

        self.horizontalLayout_18.addWidget(self.btn_editor_map_select)

        self.btn_editor_map_mark = QPushButton(self.editor_map_toolbar)
        self.buttonGroup.addButton(self.btn_editor_map_mark)
        self.btn_editor_map_mark.setObjectName(u"btn_editor_map_mark")
        self.btn_editor_map_mark.setCheckable(True)

        self.horizontalLayout_18.addWidget(self.btn_editor_map_mark)

        self.btn_editor_map_snap = QPushButton(self.editor_map_toolbar)
        self.btn_editor_map_snap.setObjectName(u"btn_editor_map_snap")
        self.btn_editor_map_snap.setCheckable(True)
        self.btn_editor_map_snap.setChecked(True)

        self.horizontalLayout_18.addWidget(self.btn_editor_map_snap)

        self.btn_editor_map_gird = QPushButton(self.editor_map_toolbar)
        self.btn_editor_map_gird.setObjectName(u"btn_editor_map_gird")
        self.btn_editor_map_gird.setCheckable(True)
        self.btn_editor_map_gird.setChecked(True)

        self.horizontalLayout_18.addWidget(self.btn_editor_map_gird)

        self.horizontalSpacer_8 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_18.addItem(self.horizontalSpacer_8)

        self.btn_editor_map_selectmap = QComboBox(self.editor_map_toolbar)
        self.btn_editor_map_selectmap.addItem("")
        self.btn_editor_map_selectmap.setObjectName(u"btn_editor_map_selectmap")
        self.btn_editor_map_selectmap.setEditable(True)

        self.horizontalLayout_18.addWidget(self.btn_editor_map_selectmap)


        self.verticalLayout_25.addWidget(self.editor_map_toolbar)

        self.editor_map_canvas = QGraphicsView(self.editor_map_mid)
        self.editor_map_canvas.setObjectName(u"editor_map_canvas")
        self.editor_map_canvas.setMinimumSize(QSize(100, 0))
        self.editor_map_canvas.setAutoFillBackground(True)
        self.editor_map_canvas.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.editor_map_canvas.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.verticalLayout_25.addWidget(self.editor_map_canvas)

        self.editor_map_info = QFrame(self.editor_map_mid)
        self.editor_map_info.setObjectName(u"editor_map_info")
        self.editor_map_info.setMinimumSize(QSize(0, 30))
        self.editor_map_info.setMaximumSize(QSize(16777215, 30))
        self.editor_map_info.setFrameShape(QFrame.Shape.StyledPanel)
        self.editor_map_info.setFrameShadow(QFrame.Shadow.Raised)
        self.horizontalLayout_19 = QHBoxLayout(self.editor_map_info)
        self.horizontalLayout_19.setSpacing(20)
        self.horizontalLayout_19.setObjectName(u"horizontalLayout_19")
        self.horizontalLayout_19.setContentsMargins(0, 0, 0, 0)
        self.horizontalSpacer_14 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_19.addItem(self.horizontalSpacer_14)

        self.label_editor_map_name = QLabel(self.editor_map_info)
        self.label_editor_map_name.setObjectName(u"label_editor_map_name")

        self.horizontalLayout_19.addWidget(self.label_editor_map_name)

        self.label_editor_map_size = QLabel(self.editor_map_info)
        self.label_editor_map_size.setObjectName(u"label_editor_map_size")

        self.horizontalLayout_19.addWidget(self.label_editor_map_size)

        self.label_editor_map_pos = QLabel(self.editor_map_info)
        self.label_editor_map_pos.setObjectName(u"label_editor_map_pos")

        self.horizontalLayout_19.addWidget(self.label_editor_map_pos)

        self.horizontalSpacer_10 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_19.addItem(self.horizontalSpacer_10)


        self.verticalLayout_25.addWidget(self.editor_map_info)


        self.horizontalLayout_24.addWidget(self.editor_map_mid)

        self.editor_map_right = QWidget(self.editor_map_widget)
        self.editor_map_right.setObjectName(u"editor_map_right")
        sizePolicy9.setHeightForWidth(self.editor_map_right.sizePolicy().hasHeightForWidth())
        self.editor_map_right.setSizePolicy(sizePolicy9)
        self.editor_map_right.setMinimumSize(QSize(240, 0))
        self.editor_map_right.setMaximumSize(QSize(240, 16777215))
        self.verticalLayout_28 = QVBoxLayout(self.editor_map_right)
        self.verticalLayout_28.setSpacing(0)
        self.verticalLayout_28.setObjectName(u"verticalLayout_28")
        self.verticalLayout_28.setContentsMargins(4, 0, 4, 0)
        self.editor_map_right_bg = QFrame(self.editor_map_right)
        self.editor_map_right_bg.setObjectName(u"editor_map_right_bg")
        self.editor_map_right_bg.setFrameShape(QFrame.Shape.NoFrame)
        self.editor_map_right_bg.setFrameShadow(QFrame.Shadow.Raised)
        self.verticalLayout_23 = QVBoxLayout(self.editor_map_right_bg)
        self.verticalLayout_23.setSpacing(0)
        self.verticalLayout_23.setObjectName(u"verticalLayout_23")
        self.verticalLayout_23.setContentsMargins(0, 0, 0, 0)
        self.label_8 = QLabel(self.editor_map_right_bg)
        self.label_8.setObjectName(u"label_8")
        self.label_8.setFrameShape(QFrame.Shape.StyledPanel)
        self.label_8.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.verticalLayout_23.addWidget(self.label_8)

        self.frame_9 = QFrame(self.editor_map_right_bg)
        self.frame_9.setObjectName(u"frame_9")
        self.frame_9.setFrameShape(QFrame.Shape.StyledPanel)
        self.frame_9.setFrameShadow(QFrame.Shadow.Raised)
        self.gridLayout = QGridLayout(self.frame_9)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setSizeConstraint(QLayout.SizeConstraint.SetDefaultConstraint)
        self.gridLayout.setHorizontalSpacing(-1)
        self.gridLayout.setContentsMargins(4, 0, 4, 0)
        self.label_16 = QLabel(self.frame_9)
        self.label_16.setObjectName(u"label_16")

        self.gridLayout.addWidget(self.label_16, 5, 0, 1, 1)

        self.label_18 = QLabel(self.frame_9)
        self.label_18.setObjectName(u"label_18")

        self.gridLayout.addWidget(self.label_18, 25, 0, 1, 1)

        self.att_gravity = QCheckBox(self.frame_9)
        self.att_gravity.setObjectName(u"att_gravity")

        self.gridLayout.addWidget(self.att_gravity, 5, 2, 1, 1)

        self.att_tile_name = QLineEdit(self.frame_9)
        self.att_tile_name.setObjectName(u"att_tile_name")

        self.gridLayout.addWidget(self.att_tile_name, 9, 2, 1, 1)

        self.label_17 = QLabel(self.frame_9)
        self.label_17.setObjectName(u"label_17")

        self.gridLayout.addWidget(self.label_17, 24, 0, 1, 1)

        self.att_col_type = QComboBox(self.frame_9)
        self.att_col_type.addItem("")
        self.att_col_type.addItem("")
        self.att_col_type.addItem("")
        self.att_col_type.addItem("")
        self.att_col_type.setObjectName(u"att_col_type")
        self.att_col_type.setEditable(True)
        self.att_col_type.setDuplicatesEnabled(False)

        self.gridLayout.addWidget(self.att_col_type, 13, 2, 1, 1)

        self.att_tag = QLineEdit(self.frame_9)
        self.att_tag.setObjectName(u"att_tag")
        self.att_tag.setEnabled(False)
        self.att_tag.setMaximumSize(QSize(16777215, 0))

        self.gridLayout.addWidget(self.att_tag, 15, 2, 1, 1)

        self.att_tile_size = QComboBox(self.frame_9)
        self.att_tile_size.addItem("")
        self.att_tile_size.addItem("")
        self.att_tile_size.addItem("")
        self.att_tile_size.setObjectName(u"att_tile_size")
        self.att_tile_size.setEditable(True)
        self.att_tile_size.setDuplicatesEnabled(False)
        self.att_tile_size.setFrame(True)

        self.gridLayout.addWidget(self.att_tile_size, 10, 2, 1, 1)

        self.horizontalLayout_12 = QHBoxLayout()
        self.horizontalLayout_12.setObjectName(u"horizontalLayout_12")
        self.label_19 = QLabel(self.frame_9)
        self.label_19.setObjectName(u"label_19")

        self.horizontalLayout_12.addWidget(self.label_19)

        self.att_mapsize_x = QLineEdit(self.frame_9)
        self.att_mapsize_x.setObjectName(u"att_mapsize_x")

        self.horizontalLayout_12.addWidget(self.att_mapsize_x)


        self.gridLayout.addLayout(self.horizontalLayout_12, 2, 2, 1, 1)

        self.map_collision = QCheckBox(self.frame_9)
        self.map_collision.setObjectName(u"map_collision")

        self.gridLayout.addWidget(self.map_collision, 17, 2, 1, 1)

        self.horizontalLayout_13 = QHBoxLayout()
        self.horizontalLayout_13.setObjectName(u"horizontalLayout_13")
        self.label_20 = QLabel(self.frame_9)
        self.label_20.setObjectName(u"label_20")

        self.horizontalLayout_13.addWidget(self.label_20)

        self.att_mapsize_y = QLineEdit(self.frame_9)
        self.att_mapsize_y.setObjectName(u"att_mapsize_y")

        self.horizontalLayout_13.addWidget(self.att_mapsize_y)


        self.gridLayout.addLayout(self.horizontalLayout_13, 3, 2, 1, 1)

        self.line_3 = QFrame(self.frame_9)
        self.line_3.setObjectName(u"line_3")
        self.line_3.setFrameShape(QFrame.Shape.HLine)
        self.line_3.setFrameShadow(QFrame.Shadow.Sunken)

        self.gridLayout.addWidget(self.line_3, 23, 0, 1, 3)

        self.att_map_name = QLineEdit(self.frame_9)
        self.att_map_name.setObjectName(u"att_map_name")

        self.gridLayout.addWidget(self.att_map_name, 1, 2, 1, 1)

        self.att_collision = QLabel(self.frame_9)
        self.att_collision.setObjectName(u"att_collision")

        self.gridLayout.addWidget(self.att_collision, 17, 0, 1, 1)

        self.horizontalSpacer_12 = QSpacerItem(30, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout.addItem(self.horizontalSpacer_12, 1, 1, 1, 1)

        self.label_14 = QLabel(self.frame_9)
        self.label_14.setObjectName(u"label_14")

        self.gridLayout.addWidget(self.label_14, 2, 0, 1, 1)

        self.label_10 = QLabel(self.frame_9)
        self.label_10.setObjectName(u"label_10")

        self.gridLayout.addWidget(self.label_10, 18, 0, 1, 1)

        self.label_9 = QLabel(self.frame_9)
        self.label_9.setObjectName(u"label_9")

        self.gridLayout.addWidget(self.label_9, 9, 0, 1, 1)

        self.horizontalLayout_16 = QHBoxLayout()
        self.horizontalLayout_16.setObjectName(u"horizontalLayout_16")
        self.label_22 = QLabel(self.frame_9)
        self.label_22.setObjectName(u"label_22")

        self.horizontalLayout_16.addWidget(self.label_22)

        self.att_mark_pos_x = QLineEdit(self.frame_9)
        self.att_mark_pos_x.setObjectName(u"att_mark_pos_x")

        self.horizontalLayout_16.addWidget(self.att_mark_pos_x)


        self.gridLayout.addLayout(self.horizontalLayout_16, 25, 2, 1, 1)

        self.line_2 = QFrame(self.frame_9)
        self.line_2.setObjectName(u"line_2")
        self.line_2.setFrameShape(QFrame.Shape.HLine)
        self.line_2.setFrameShadow(QFrame.Shadow.Sunken)

        self.gridLayout.addWidget(self.line_2, 7, 0, 1, 3)

        self.att_mark_name = QLineEdit(self.frame_9)
        self.att_mark_name.setObjectName(u"att_mark_name")

        self.gridLayout.addWidget(self.att_mark_name, 24, 2, 1, 1)

        self.horizontalLayout_17 = QHBoxLayout()
        self.horizontalLayout_17.setObjectName(u"horizontalLayout_17")
        self.label_23 = QLabel(self.frame_9)
        self.label_23.setObjectName(u"label_23")

        self.horizontalLayout_17.addWidget(self.label_23)

        self.att_mark_pos_y = QLineEdit(self.frame_9)
        self.att_mark_pos_y.setObjectName(u"att_mark_pos_y")

        self.horizontalLayout_17.addWidget(self.att_mark_pos_y)


        self.gridLayout.addLayout(self.horizontalLayout_17, 26, 2, 1, 1)

        self.label_12 = QLabel(self.frame_9)
        self.label_12.setObjectName(u"label_12")

        self.gridLayout.addWidget(self.label_12, 13, 0, 1, 1)

        self.label_15 = QLabel(self.frame_9)
        self.label_15.setObjectName(u"label_15")

        self.gridLayout.addWidget(self.label_15, 10, 0, 1, 1)

        self.label_13 = QLabel(self.frame_9)
        self.label_13.setObjectName(u"label_13")

        self.gridLayout.addWidget(self.label_13, 1, 0, 1, 1)

        self.att_tile_id = QLabel(self.frame_9)
        self.att_tile_id.setObjectName(u"att_tile_id")

        self.gridLayout.addWidget(self.att_tile_id, 18, 2, 1, 1)

        self.lineEdit = QLineEdit(self.frame_9)
        self.lineEdit.setObjectName(u"lineEdit")

        self.gridLayout.addWidget(self.lineEdit, 14, 2, 1, 1)


        self.verticalLayout_23.addWidget(self.frame_9)

        self.label_24 = QLabel(self.editor_map_right_bg)
        self.label_24.setObjectName(u"label_24")
        self.label_24.setFrameShape(QFrame.Shape.StyledPanel)
        self.label_24.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.verticalLayout_23.addWidget(self.label_24)

        self.editor_map_layer_list = QTreeWidget(self.editor_map_right_bg)
        self.editor_map_layer_list.setObjectName(u"editor_map_layer_list")
        self.editor_map_layer_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.editor_map_layer_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.editor_map_layer_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.editor_map_layer_list.setSupportedDragActions(Qt.DropAction.CopyAction|Qt.DropAction.MoveAction)
        self.editor_map_layer_list.header().setVisible(True)

        self.verticalLayout_23.addWidget(self.editor_map_layer_list)

        self.layer_editor_toolbar = QFrame(self.editor_map_right_bg)
        self.layer_editor_toolbar.setObjectName(u"layer_editor_toolbar")
        self.layer_editor_toolbar.setMinimumSize(QSize(0, 30))
        self.layer_editor_toolbar.setMaximumSize(QSize(16777215, 30))
        self.layer_editor_toolbar.setFrameShape(QFrame.Shape.StyledPanel)
        self.layer_editor_toolbar.setFrameShadow(QFrame.Shadow.Raised)
        self.horizontalLayout_21 = QHBoxLayout(self.layer_editor_toolbar)
        self.horizontalLayout_21.setSpacing(1)
        self.horizontalLayout_21.setObjectName(u"horizontalLayout_21")
        self.horizontalLayout_21.setContentsMargins(0, 0, 0, 0)
        self.btn_editor_map_layer_tiled = QPushButton(self.layer_editor_toolbar)
        self.btn_editor_map_layer_tiled.setObjectName(u"btn_editor_map_layer_tiled")

        self.horizontalLayout_21.addWidget(self.btn_editor_map_layer_tiled)

        self.btn_editor_map_layer_image = QPushButton(self.layer_editor_toolbar)
        self.btn_editor_map_layer_image.setObjectName(u"btn_editor_map_layer_image")

        self.horizontalLayout_21.addWidget(self.btn_editor_map_layer_image)

        self.btn_editor_map_layer_del = QPushButton(self.layer_editor_toolbar)
        self.btn_editor_map_layer_del.setObjectName(u"btn_editor_map_layer_del")

        self.horizontalLayout_21.addWidget(self.btn_editor_map_layer_del)

        self.btn_editor_map_layer_up = QPushButton(self.layer_editor_toolbar)
        self.btn_editor_map_layer_up.setObjectName(u"btn_editor_map_layer_up")

        self.horizontalLayout_21.addWidget(self.btn_editor_map_layer_up)

        self.btn_editor_map_layer_down = QPushButton(self.layer_editor_toolbar)
        self.btn_editor_map_layer_down.setObjectName(u"btn_editor_map_layer_down")

        self.horizontalLayout_21.addWidget(self.btn_editor_map_layer_down)


        self.verticalLayout_23.addWidget(self.layer_editor_toolbar)


        self.verticalLayout_28.addWidget(self.editor_map_right_bg)


        self.horizontalLayout_24.addWidget(self.editor_map_right)


        self.verticalLayout_29.addWidget(self.editor_map_widget)

        self.editor_stacked.addWidget(self.editor_map_web)

        self.verticalLayout_19.addWidget(self.editor_stacked)

        self.change_page.addWidget(self.edit_stage_frame)
        self.fullscreen = QWidget()
        self.fullscreen.setObjectName(u"fullscreen")
        sizePolicy4.setHeightForWidth(self.fullscreen.sizePolicy().hasHeightForWidth())
        self.fullscreen.setSizePolicy(sizePolicy4)
        self.fullscreen.setMinimumSize(QSize(0, 0))
        self.verticalLayout_8 = QVBoxLayout(self.fullscreen)
        self.verticalLayout_8.setSpacing(0)
        self.verticalLayout_8.setObjectName(u"verticalLayout_8")
        self.verticalLayout_8.setContentsMargins(0, 0, 0, 0)
        self.bg_layout = QFrame(self.fullscreen)
        self.bg_layout.setObjectName(u"bg_layout")
        sizePolicy11.setHeightForWidth(self.bg_layout.sizePolicy().hasHeightForWidth())
        self.bg_layout.setSizePolicy(sizePolicy11)
        self.bg_layout.setStyleSheet(u"")
        self.bg_layout.setFrameShape(QFrame.Shape.StyledPanel)
        self.bg_layout.setFrameShadow(QFrame.Shadow.Raised)
        self.horizontalLayout_10 = QHBoxLayout(self.bg_layout)
        self.horizontalLayout_10.setSpacing(0)
        self.horizontalLayout_10.setObjectName(u"horizontalLayout_10")
        self.horizontalLayout_10.setContentsMargins(0, 0, 0, 0)
        self.horizontalSpacer_4 = QSpacerItem(40, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_10.addItem(self.horizontalSpacer_4)

        self.central_stage_wrapper = QFrame(self.bg_layout)
        self.central_stage_wrapper.setObjectName(u"central_stage_wrapper")
        sizePolicy12 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        sizePolicy12.setHorizontalStretch(0)
        sizePolicy12.setVerticalStretch(0)
        sizePolicy12.setHeightForWidth(self.central_stage_wrapper.sizePolicy().hasHeightForWidth())
        self.central_stage_wrapper.setSizePolicy(sizePolicy12)
        self.central_stage_wrapper.setStyleSheet(u"")
        self.central_stage_wrapper.setFrameShape(QFrame.Shape.StyledPanel)
        self.central_stage_wrapper.setFrameShadow(QFrame.Shadow.Raised)
        self.verticalLayout_11 = QVBoxLayout(self.central_stage_wrapper)
        self.verticalLayout_11.setSpacing(4)
        self.verticalLayout_11.setObjectName(u"verticalLayout_11")
        self.verticalLayout_11.setContentsMargins(0, 0, 0, 0)
        self.fullscreen_tool_bar = QFrame(self.central_stage_wrapper)
        self.fullscreen_tool_bar.setObjectName(u"fullscreen_tool_bar")
        sizePolicy3.setHeightForWidth(self.fullscreen_tool_bar.sizePolicy().hasHeightForWidth())
        self.fullscreen_tool_bar.setSizePolicy(sizePolicy3)
        self.fullscreen_tool_bar.setMinimumSize(QSize(0, 30))
        self.fullscreen_tool_bar.setMaximumSize(QSize(16777215, 30))
        self.fullscreen_tool_bar.setFrameShape(QFrame.Shape.StyledPanel)
        self.fullscreen_tool_bar.setFrameShadow(QFrame.Shadow.Raised)
        self.horizontalLayout_9 = QHBoxLayout(self.fullscreen_tool_bar)
        self.horizontalLayout_9.setSpacing(5)
        self.horizontalLayout_9.setObjectName(u"horizontalLayout_9")
        self.horizontalLayout_9.setContentsMargins(5, 0, 5, 0)
        self.fullscreen_btn_run = QPushButton(self.fullscreen_tool_bar)
        self.fullscreen_btn_run.setObjectName(u"fullscreen_btn_run")
        self.fullscreen_btn_run.setMinimumSize(QSize(24, 24))
        self.fullscreen_btn_run.setMaximumSize(QSize(24, 24))
        self.fullscreen_btn_run.setStyleSheet(u"")
        self.fullscreen_btn_run.setIcon(icon7)
        self.fullscreen_btn_run.setCheckable(True)

        self.horizontalLayout_9.addWidget(self.fullscreen_btn_run)

        self.fullscreen_btn_stop = QPushButton(self.fullscreen_tool_bar)
        self.fullscreen_btn_stop.setObjectName(u"fullscreen_btn_stop")
        self.fullscreen_btn_stop.setMinimumSize(QSize(24, 24))
        self.fullscreen_btn_stop.setMaximumSize(QSize(24, 24))
        self.fullscreen_btn_stop.setIcon(icon8)
        self.fullscreen_btn_stop.setCheckable(False)
        self.fullscreen_btn_stop.setAutoExclusive(True)

        self.horizontalLayout_9.addWidget(self.fullscreen_btn_stop)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_9.addItem(self.horizontalSpacer)

        self.fullscreen_btn_unfull = QPushButton(self.fullscreen_tool_bar)
        self.fullscreen_btn_unfull.setObjectName(u"fullscreen_btn_unfull")
        self.fullscreen_btn_unfull.setMinimumSize(QSize(24, 24))
        self.fullscreen_btn_unfull.setMaximumSize(QSize(24, 24))
        icon16 = QIcon()
        icon16.addFile(u":/icons/icon--unfullscreen.svg", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.fullscreen_btn_unfull.setIcon(icon16)
        self.fullscreen_btn_unfull.setIconSize(QSize(20, 20))
        self.fullscreen_btn_unfull.setAutoExclusive(False)

        self.horizontalLayout_9.addWidget(self.fullscreen_btn_unfull)


        self.verticalLayout_11.addWidget(self.fullscreen_tool_bar)

        self.fullscreen_view_frame = QFrame(self.central_stage_wrapper)
        self.fullscreen_view_frame.setObjectName(u"fullscreen_view_frame")
        sizePolicy13 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy13.setHorizontalStretch(0)
        sizePolicy13.setVerticalStretch(0)
        sizePolicy13.setHeightForWidth(self.fullscreen_view_frame.sizePolicy().hasHeightForWidth())
        self.fullscreen_view_frame.setSizePolicy(sizePolicy13)
        self.fullscreen_view_frame.setMinimumSize(QSize(0, 0))
        self.fullscreen_view_frame.setStyleSheet(u"")
        self.fullscreen_view_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.fullscreen_view_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.verticalLayout_7 = QVBoxLayout(self.fullscreen_view_frame)
        self.verticalLayout_7.setSpacing(0)
        self.verticalLayout_7.setObjectName(u"verticalLayout_7")
        self.verticalLayout_7.setContentsMargins(0, 0, 0, 0)

        self.verticalLayout_11.addWidget(self.fullscreen_view_frame)

        self.verticalLayout_11.setStretch(1, 1)

        self.horizontalLayout_10.addWidget(self.central_stage_wrapper, 0, Qt.AlignmentFlag.AlignHCenter|Qt.AlignmentFlag.AlignTop)

        self.horizontalSpacer_5 = QSpacerItem(40, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_10.addItem(self.horizontalSpacer_5)

        self.horizontalLayout_10.setStretch(0, 1)
        self.horizontalLayout_10.setStretch(1, 4)
        self.horizontalLayout_10.setStretch(2, 1)

        self.verticalLayout_8.addWidget(self.bg_layout)

        self.change_page.addWidget(self.fullscreen)

        self.verticalLayout_4.addWidget(self.change_page)


        self.retranslateUi(Form)

        self.change_page.setCurrentIndex(0)
        self.editor_stacked.setCurrentIndex(0)
        self.btn_outline_sprite.setDefault(False)
        self.btn_outline_sound.setDefault(False)
        self.btn_outline_code.setDefault(False)
        self.outline_stracked.setCurrentIndex(1)
        self.code_stacked.setCurrentIndex(-1)
        self.att_col_type.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(Form)
    # setupUi

    def retranslateUi(self, Form):
        Form.setWindowTitle(QCoreApplication.translate("Form", u"Form", None))
        self.btn_logo.setText("")
        self.btn_file.setText(QCoreApplication.translate("Form", u"\u6587\u4ef6", None))
        self.btn_code_editor.setText(QCoreApplication.translate("Form", u"\u4ee3\u7801", None))
        self.btn_sprite_editor.setText(QCoreApplication.translate("Form", u"\u89d2\u8272", None))
        self.btn_map_editor.setText(QCoreApplication.translate("Form", u"\u5730\u56fe", None))
        self.btn_save.setText(QCoreApplication.translate("Form", u"\u58f0\u97f3", None))
        self.btn_help.setText("")
        self.btn_run.setText("")
        self.btn_stop.setText("")
        self.btn_full_screen.setText("")
        self.btn_outline_sprite.setText(QCoreApplication.translate("Form", u"\u89d2\u8272", None))
        self.btn_outline_bg.setText(QCoreApplication.translate("Form", u"\u573a\u666f", None))
        self.btn_outline_sound.setText(QCoreApplication.translate("Form", u"\u58f0\u97f3", None))
        self.btn_outline_code.setText(QCoreApplication.translate("Form", u"\u4ee3\u7801", None))
        self.label_4.setText(QCoreApplication.translate("Form", u"\u58f0\u97f3\u9875\u9762", None))
        self.btn_add_tab.setText(QCoreApplication.translate("Form", u"+", None))
        self.animate_label.setText(QCoreApplication.translate("Form", u"ANIMATION", None))
        self.animate_preview.setText("")
        self.btn_preview_prev.setText("")
        self.btn_preview_play.setText("")
        self.btn_preview_next.setText("")
        self.btn_preview_scale.setText("")
        self.btn_preview_change_bg.setText("")
        self.btn_preview_add.setText("")
        self.btn_res_list_open.setText(QCoreApplication.translate("Form", u"\u9009\u62e9", None))
        self.btn_res_list_upload.setText(QCoreApplication.translate("Form", u"\u4e0a\u4f20", None))
        self.btn_res_list_clear.setText(QCoreApplication.translate("Form", u"\u6e05\u7a7a", None))
        self.btn_res_col_move.setText(QCoreApplication.translate("Form", u"\u79fb", None))
        self.btn_res_col_add.setText(QCoreApplication.translate("Form", u"\u52a0", None))
        self.btn_res_col_del.setText(QCoreApplication.translate("Form", u"\u5220", None))
        self.btn_res_col_reset.setText(QCoreApplication.translate("Form", u"\u91cd", None))
        self.btn_res_col_snap.setText(QCoreApplication.translate("Form", u"\u5438", None))
        self.label_res_list_name.setText(QCoreApplication.translate("Form", u"\u8d44\u6e90:foreasdnew", None))
        self.label_res_list_id.setText(QCoreApplication.translate("Form", u"ID:12", None))
        self.label_res_list_size.setText(QCoreApplication.translate("Form", u"\u5c3a\u5bf8:16x16", None))
        self.btn_editor_map_new.setText(QCoreApplication.translate("Form", u"\u65b0\u5efa", None))
        self.btn_editor_map_import.setText(QCoreApplication.translate("Form", u"\u5bfc\u5165", None))
        self.btn_editor_map_export.setText(QCoreApplication.translate("Form", u"\u5bfc\u51fa", None))
        self.btn_editor_map_move.setText(QCoreApplication.translate("Form", u"\u79fb\u52a8", None))
        self.btn_editor_map_draw.setText(QCoreApplication.translate("Form", u"\u7ed8\u5236", None))
        self.btn_editor_map_erase.setText(QCoreApplication.translate("Form", u"\u64e6\u9664", None))
        self.btn_editor_map_select.setText(QCoreApplication.translate("Form", u"\u9009\u533a", None))
        self.btn_editor_map_mark.setText(QCoreApplication.translate("Form", u"\u6807\u8bb0", None))
        self.btn_editor_map_snap.setText(QCoreApplication.translate("Form", u"\u5438\u9644", None))
        self.btn_editor_map_gird.setText(QCoreApplication.translate("Form", u"\u7f51", None))
        self.btn_editor_map_selectmap.setItemText(0, QCoreApplication.translate("Form", u"\u65b0\u5efa\u9879\u76ee", None))

        self.label_editor_map_name.setText(QCoreApplication.translate("Form", u"\u5730\u56fe1", None))
        self.label_editor_map_size.setText(QCoreApplication.translate("Form", u"\u573a\u666f\u5927\u5c0f:40x20", None))
        self.label_editor_map_pos.setText(QCoreApplication.translate("Form", u"X:187 Y:339", None))
        self.label_8.setText(QCoreApplication.translate("Form", u"\u5c5e\u6027", None))
        self.label_16.setText(QCoreApplication.translate("Form", u"\u5730\u56fe\u91cd\u529b", None))
        self.label_18.setText(QCoreApplication.translate("Form", u"\u6807\u8bb0\u4f4d\u7f6e", None))
        self.att_gravity.setText(QCoreApplication.translate("Form", u"\u542f\u7528", None))
        self.att_tile_name.setText(QCoreApplication.translate("Form", u"\u5730\u56fe1", None))
        self.label_17.setText(QCoreApplication.translate("Form", u"\u6807\u8bb0\u540d\u79f0", None))
        self.att_col_type.setItemText(0, QCoreApplication.translate("Form", u"\u5899\u4f53", None))
        self.att_col_type.setItemText(1, QCoreApplication.translate("Form", u"\u8df3\u677f", None))
        self.att_col_type.setItemText(2, QCoreApplication.translate("Form", u"\u80cc\u666f", None))
        self.att_col_type.setItemText(3, QCoreApplication.translate("Form", u"\u81ea\u5b9a\u4e49", None))

        self.att_col_type.setCurrentText(QCoreApplication.translate("Form", u"\u5899\u4f53", None))
        self.att_tag.setText("")
        self.att_tile_size.setItemText(0, QCoreApplication.translate("Form", u"16x16", None))
        self.att_tile_size.setItemText(1, QCoreApplication.translate("Form", u"32x32", None))
        self.att_tile_size.setItemText(2, QCoreApplication.translate("Form", u"64x64", None))

        self.label_19.setText(QCoreApplication.translate("Form", u"X", None))
        self.att_mapsize_x.setText(QCoreApplication.translate("Form", u"100", None))
        self.map_collision.setText(QCoreApplication.translate("Form", u"\u542f\u7528", None))
        self.label_20.setText(QCoreApplication.translate("Form", u"Y", None))
        self.att_mapsize_y.setText(QCoreApplication.translate("Form", u"100", None))
        self.att_map_name.setText(QCoreApplication.translate("Form", u"\u5730\u56fe1", None))
        self.att_collision.setText(QCoreApplication.translate("Form", u"\u78b0\u649e", None))
        self.label_14.setText(QCoreApplication.translate("Form", u"\u5730\u56fe\u5c3a\u5bf8", None))
        self.label_10.setText(QCoreApplication.translate("Form", u"\u7f16\u53f7", None))
        self.label_9.setText(QCoreApplication.translate("Form", u"\u540d\u79f0", None))
        self.label_22.setText(QCoreApplication.translate("Form", u"X", None))
        self.att_mark_pos_x.setText(QCoreApplication.translate("Form", u"100", None))
        self.att_mark_name.setText(QCoreApplication.translate("Form", u"\u51fa\u751f\u70b9", None))
        self.label_23.setText(QCoreApplication.translate("Form", u"Y", None))
        self.att_mark_pos_y.setText(QCoreApplication.translate("Form", u"100", None))
        self.label_12.setText(QCoreApplication.translate("Form", u"\u7269\u7406\u5c5e\u6027", None))
        self.label_15.setText(QCoreApplication.translate("Form", u"\u56fe\u5757\u5c3a\u5bf8", None))
        self.label_13.setText(QCoreApplication.translate("Form", u"\u5730\u56fe\u540d\u79f0", None))
        self.att_tile_id.setText(QCoreApplication.translate("Form", u"19", None))
        self.label_24.setText(QCoreApplication.translate("Form", u"\u56fe\u5c42", None))
        ___qtreewidgetitem = self.editor_map_layer_list.headerItem()
        ___qtreewidgetitem.setText(2, QCoreApplication.translate("Form", u"\u9501\u5b9a", None));
        ___qtreewidgetitem.setText(1, QCoreApplication.translate("Form", u"\u540d\u79f0", None));
        ___qtreewidgetitem.setText(0, QCoreApplication.translate("Form", u"\u663e\u793a", None));
        self.btn_editor_map_layer_tiled.setText(QCoreApplication.translate("Form", u"Tiled", None))
        self.btn_editor_map_layer_image.setText(QCoreApplication.translate("Form", u"IMG", None))
        self.btn_editor_map_layer_del.setText(QCoreApplication.translate("Form", u"\u5220", None))
        self.btn_editor_map_layer_up.setText(QCoreApplication.translate("Form", u"\u4e0a", None))
        self.btn_editor_map_layer_down.setText(QCoreApplication.translate("Form", u"\u4e0b", None))
        self.fullscreen_btn_run.setText("")
        self.fullscreen_btn_stop.setText("")
        self.fullscreen_btn_unfull.setText("")
    # retranslateUi

