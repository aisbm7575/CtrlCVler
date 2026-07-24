import sys
import time
import json
import os
import ctypes
import winreg
import keyboard
from pynput import mouse
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QComboBox, QListWidget, QPushButton, 
                             QSlider, QLabel, QInputDialog, QMessageBox, QMenu,
                             QCheckBox, QSystemTrayIcon, QStyle, QFrame)
from PyQt6.QtCore import Qt, QMimeData, QThread, QTimer
from PyQt6.QtGui import QDrag, QFont

DATA_FILE = "data.json"
REG_APP_NAME = "CtrlCVler"

class MouseHookThread(QThread):
    def __init__(self):
        super().__init__()
        self.right_press_time = 0
        self.middle_press_time = 0
        self.last_paste_time = 0 
        self.listener = None

    def on_click(self, x, y, button, pressed):
        if button == mouse.Button.right:
            if pressed: 
                self.right_press_time = time.time()
            else:
                current_time = time.time()
                if current_time - self.right_press_time >= 0.5:
                    if current_time - self.last_paste_time > 1.0:
                        self.last_paste_time = current_time
                        keyboard.send('esc') 
                        time.sleep(0.1)
                        keyboard.send('ctrl+v')
                        
        elif button == mouse.Button.middle:
            if pressed: 
                self.middle_press_time = time.time()
            else:
                current_time = time.time()
                if current_time - self.middle_press_time < 1.0: 
                    if current_time - self.last_paste_time > 0.5:
                        self.last_paste_time = current_time
                        time.sleep(0.1)
                        keyboard.send('ctrl+v')

    def run(self):
        with mouse.Listener(on_click=self.on_click) as self.listener:
            self.listener.join()
            
    def stop(self):
        if self.listener: self.listener.stop()

class DraggableListWidget(QListWidget):
    def __init__(self):
        super().__init__()
        self.setDragEnabled(True)

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if item is None: return
        drag = QDrag(self)
        mimeData = QMimeData()
        mimeData.setText(item.text())
        drag.setMimeData(mimeData)
        drag.exec(supportedActions)

class CtrlCVlerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.is_dark_mode = False
        self.ignore_clipboard = False 
        
        self.load_data()
        self.initUI()
        self.setup_tray()
        
        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self.on_clipboard_changed)
        
        self.mouse_thread = MouseHookThread()
        self.mouse_thread.start()

    def load_data(self):
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                self.app_data = json.load(f)
        else:
            self.app_data = {
                "최신 수집": [],
                "기본 인사말": ["안녕하세요, 연락 주셔서 감사합니다."],
                "자주 쓰는 코드": ["def hello():\n    print('hi')"]
            }
        
        if "최신 수집" not in self.app_data:
            self.app_data = {"최신 수집": [], **self.app_data}

    def save_data(self):
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.app_data, f, ensure_ascii=False, indent=4)

    def initUI(self):
        self.setWindowTitle("Ctrl C+Vler")
        # 라벨이 빠진 만큼 창의 전체 가로폭을 300에서 260으로 축소
        self.setGeometry(100, 100, 260, 600)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        self.setFont(QFont("Malgun Gothic", 10))

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout()
        main_widget.setLayout(layout)

        # 섹터 및 상단 버튼 레이아웃
        sector_layout = QHBoxLayout()
        sector_layout.setContentsMargins(0, 0, 0, 0) 
        
        # '섹터:' 라벨 삭제 완료
        
        self.sector_combo = QComboBox()
        self.sector_combo.setFixedHeight(28) 
        self.sector_combo.addItems(self.app_data.keys())
        self.sector_combo.currentTextChanged.connect(self.update_list)
        
        # [+] 버튼 정중앙 정렬 유지
        btn_add_sector = QPushButton("+")
        btn_add_sector.setObjectName("btnAddSector")
        btn_add_sector.setFixedSize(28, 28)
        plus_font = QFont("Malgun Gothic", 16, QFont.Weight.Bold)
        btn_add_sector.setFont(plus_font)
        btn_add_sector.setToolTip("섹터 추가") 
        btn_add_sector.clicked.connect(self.add_sector)
        
        btn_edit_sector = QPushButton("✏️")
        btn_edit_sector.setFixedSize(28, 28)
        btn_edit_sector.setToolTip("섹터 이름 수정") 
        btn_edit_sector.clicked.connect(self.edit_sector)
        
        btn_del_sector = QPushButton("🗑️")
        btn_del_sector.setFixedSize(28, 28)
        btn_del_sector.setToolTip("섹터 삭제") 
        btn_del_sector.clicked.connect(self.delete_sector)

        btn_info = QPushButton("ℹ️")
        btn_info.setFixedSize(28, 28)
        btn_info.setToolTip("프로그램 정보")
        btn_info.clicked.connect(self.show_info)

        btn_options = QPushButton("⚙️")
        btn_options.setFixedSize(28, 28)
        btn_options.setToolTip("설정 열기/닫기")
        btn_options.clicked.connect(self.toggle_settings)

        sector_layout.addWidget(self.sector_combo)
        sector_layout.addWidget(btn_add_sector)
        sector_layout.addWidget(btn_edit_sector)
        sector_layout.addWidget(btn_del_sector)
        sector_layout.addWidget(btn_info)
        sector_layout.addWidget(btn_options)
        layout.addLayout(sector_layout)

        # 리스트 위젯
        self.list_widget = DraggableListWidget()
        self.list_widget.itemClicked.connect(self.copy_to_clipboard)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)
        
        layout.addWidget(self.list_widget)
        self.update_list()

        # 항목 관리 버튼 레이아웃
        item_manage_layout = QHBoxLayout()
        btn_add_item = QPushButton("항목 추가")
        btn_add_item.clicked.connect(self.add_item)
        
        btn_del_item = QPushButton("선택 삭제")
        btn_del_item.clicked.connect(self.delete_item)
        
        btn_del_all = QPushButton("전체 삭제")
        btn_del_all.clicked.connect(self.delete_all_items)
        
        item_manage_layout.addWidget(btn_add_item)
        item_manage_layout.addWidget(btn_del_item)
        item_manage_layout.addWidget(btn_del_all)
        layout.addLayout(item_manage_layout)

        guide_label = QLabel("💡 다른 창에서 Ctrl+C시 '최신 수집'에 자동저장\n💡 항목 우클릭 시 다른 섹터로 이동 가능")
        guide_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(guide_label)

        # --- [숨김/열림 설정 패널 영역] ---
        self.settings_panel = QFrame()
        self.settings_panel.setFrameShape(QFrame.Shape.StyledPanel)
        settings_layout = QVBoxLayout()
        self.settings_panel.setLayout(settings_layout)

        opacity_layout = QHBoxLayout()
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(20, 100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.valueChanged.connect(self.change_opacity)
        opacity_layout.addWidget(QLabel("투명도:"))
        opacity_layout.addWidget(self.opacity_slider)
        settings_layout.addLayout(opacity_layout)

        self.autostart_cb = QCheckBox("윈도우 시작 시 자동 실행")
        self.autostart_cb.setChecked(self.is_autostart_enabled())
        self.autostart_cb.toggled.connect(self.toggle_autostart)
        settings_layout.addWidget(self.autostart_cb)

        self.mode_btn = QPushButton("다크 모드로 전환")
        self.mode_btn.clicked.connect(self.toggle_mode)
        settings_layout.addWidget(self.mode_btn)

        self.settings_panel.setVisible(False)
        layout.addWidget(self.settings_panel)

        self.apply_theme()

    def toggle_settings(self):
        is_visible = self.settings_panel.isVisible()
        self.settings_panel.setVisible(not is_visible)

    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self.tray_icon.setIcon(icon)

        tray_menu = QMenu()
        show_action = tray_menu.addAction("열기")
        show_action.triggered.connect(self.show_window)

        quit_action = tray_menu.addAction("종료")
        quit_action.triggered.connect(self.force_quit)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def show_window(self):
        self.showNormal()
        self.activateWindow()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show_window()

    def force_quit(self):
        self.mouse_thread.stop()
        self.mouse_thread.quit()
        self.mouse_thread.wait()
        QApplication.quit()

    def closeEvent(self, event):
        if self.tray_icon.isVisible():
            self.hide()
            self.tray_icon.showMessage(
                "Ctrl C+Vler",
                "프로그램이 트레이 아이콘으로 최소화되었습니다.",
                QSystemTrayIcon.MessageIcon.Information,
                1500
            )
            event.ignore()
        else:
            self.force_quit()
            event.accept()

    def is_autostart_enabled(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, REG_APP_NAME)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            return False
        except Exception:
            return False

    def toggle_autostart(self, enabled):
        reg_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_ALL_ACCESS)
            if enabled:
                if getattr(sys, 'frozen', False):
                    exec_path = f'"{sys.executable}"'
                else:
                    exec_path = f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'
                winreg.SetValueEx(key, REG_APP_NAME, 0, winreg.REG_SZ, exec_path)
            else:
                try:
                    winreg.DeleteValue(key, REG_APP_NAME)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            QMessageBox.warning(self, "설정 실패", f"시작 프로그램 설정 중 오류가 발생했습니다:\n{e}")

    def show_info(self):
        QMessageBox.information(self, "Ctrl C+Vler 정보", 
            "Ctrl C+Vler v1.0\n\n"
            "나만의 빠르고 편리한 클립보드 매니저입니다.\n\n"
            "[Open Source Licenses]\n"
            "- PyQt6 (GPLv3)\n"
            "- pynput (MIT)\n"
            "- keyboard (MIT)"
        )

    def on_clipboard_changed(self):
        if self.ignore_clipboard:
            return
            
        mime_data = self.clipboard.mimeData()
        if mime_data.hasText():
            text = mime_data.text().strip()
            if not text: return
            
            if text in self.app_data["최신 수집"]:
                return
                
            self.app_data["최신 수집"].append(text)
            self.save_data()
            
            if self.sector_combo.currentText() == "최신 수집":
                self.update_list()

    def show_context_menu(self, position):
        item = self.list_widget.itemAt(position)
        if not item: return

        menu = QMenu()
        move_menu = menu.addMenu("➡️ 다른 섹터로 이동")

        current_sector = self.sector_combo.currentText()
        has_other_sectors = False
        
        for sector in self.app_data.keys():
            if sector != current_sector:
                has_other_sectors = True
                action = move_menu.addAction(sector)
                action.triggered.connect(lambda checked, s=sector: self.move_item(item, s))

        if not has_other_sectors:
            move_menu.setEnabled(False)

        menu.exec(self.list_widget.mapToGlobal(position))

    def move_item(self, item, target_sector):
        current_sector = self.sector_combo.currentText()
        row = self.list_widget.row(item)
        
        text_to_move = self.app_data[current_sector][row]
        
        if text_to_move in self.app_data[target_sector]:
            QMessageBox.information(self, "이동 불가", f"'{target_sector}' 섹터에 이미 동일한 내용이 존재합니다.")
            return
        
        text = self.app_data[current_sector].pop(row)
        self.app_data[target_sector].append(text)
        
        self.update_list()
        self.save_data()

    def add_sector(self):
        text, ok = QInputDialog.getText(self, '섹터 추가', '새로운 섹터 이름을 입력하세요:')
        if ok and text and text not in self.app_data:
            self.app_data[text] = []
            self.sector_combo.addItem(text)
            self.sector_combo.setCurrentText(text)
            self.save_data()

    def edit_sector(self):
        current = self.sector_combo.currentText()
        if current == "최신 수집":
            QMessageBox.warning(self, "수정 불가", "'최신 수집' 섹터의 이름은 변경할 수 없습니다.")
            return
            
        if not current: return
        text, ok = QInputDialog.getText(self, '섹터 수정', '변경할 이름을 입력하세요:', text=current)
        if ok and text and text != current and text not in self.app_data:
            self.app_data[text] = self.app_data.pop(current)
            idx = self.sector_combo.currentIndex()
            self.sector_combo.setItemText(idx, text)
            self.save_data()

    def delete_sector(self):
        current = self.sector_combo.currentText()
        if current == "최신 수집":
            QMessageBox.warning(self, "삭제 불가", "'최신 수집' 섹터는 삭제할 수 없습니다.")
            return
            
        if not current: return
        reply = QMessageBox.question(self, '섹터 삭제', f"'{current}' 섹터와 포함된 모든 항목을 삭제하시겠습니까?", 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            del self.app_data[current]
            self.sector_combo.removeItem(self.sector_combo.currentIndex())
            self.save_data()

    def update_list(self):
        self.list_widget.clear()
        current_sector = self.sector_combo.currentText()
        if current_sector in self.app_data:
            self.list_widget.addItems(self.app_data[current_sector])
            
        if current_sector == "최신 수집":
            self.list_widget.scrollToBottom()

    def add_item(self):
        current_sector = self.sector_combo.currentText()
        if not current_sector: return
        text, ok = QInputDialog.getMultiLineText(self, '항목 추가', '복사할 내용을 입력하세요:')
        if ok and text.strip():
            self.app_data[current_sector].append(text)
            self.update_list()
            self.save_data()

    def delete_item(self):
        current_sector = self.sector_combo.currentText()
        current_row = self.list_widget.currentRow()
        if current_sector and current_row >= 0:
            del self.app_data[current_sector][current_row]
            self.update_list()
            self.save_data()

    def delete_all_items(self):
        current_sector = self.sector_combo.currentText()
        if not current_sector:
            return
            
        if not self.app_data.get(current_sector):
            QMessageBox.information(self, '알림', '삭제할 항목이 없습니다.')
            return

        reply = QMessageBox.question(
            self, 
            '전체 삭제 확인', 
            f"'{current_sector}' 섹터의 모든 항목을 삭제하시겠습니까?\n(이 작업은 되돌릴 수 없습니다.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.app_data[current_sector] = []
            self.save_data()
            self.update_list()

    def copy_to_clipboard(self, item):
        self.ignore_clipboard = True 
        self.clipboard.setText(item.text())
        self.setWindowTitle("Ctrl C+Vler - 복사완료!")
        QTimer.singleShot(100, self.reset_clipboard_flag)
        
    def reset_clipboard_flag(self):
        self.ignore_clipboard = False
        self.setWindowTitle("Ctrl C+Vler")

    def change_opacity(self, value):
        self.setWindowOpacity(value / 100.0)

    def toggle_mode(self):
        self.is_dark_mode = not self.is_dark_mode
        self.mode_btn.setText("화이트 모드로 전환" if self.is_dark_mode else "다크 모드로 전환")
        self.apply_theme()

    def apply_theme(self):
        try:
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            set_window_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
            hwnd = int(self.winId())
            value = ctypes.c_int(1 if self.is_dark_mode else 0)
            set_window_attribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value))
        except Exception:
            pass 
        
        if self.is_dark_mode:
            self.setStyleSheet("""
                QMainWindow { background-color: #2b2b2b; }
                QLabel, QCheckBox { color: #ffffff; }
                QListWidget { background-color: #3c3f41; color: #ffffff; border: 1px solid #555; outline: 0; }
                QListWidget::item:hover { background-color: #4a4d50; }
                QListWidget::item:selected { background-color: #5a5d60; color: #ffffff; } 
                QPushButton, QComboBox { background-color: #555; color: white; border: 1px solid #777; padding: 0px 5px; }
                #btnAddSector { padding: 0px; padding-bottom: 4px; }
                QMenu { background-color: #3c3f41; color: white; border: 1px solid #555; }
                QMenu::item:selected { background-color: #555; }
                QFrame { border: 1px solid #444; border-radius: 4px; margin-top: 5px; }
            """)
        else:
            self.setStyleSheet("""
                QMainWindow { background-color: #f0f0f0; }
                QLabel, QCheckBox { color: #000000; }
                QListWidget { background-color: #ffffff; color: #000000; border: 1px solid #ccc; outline: 0; }
                QListWidget::item:hover { background-color: #f0f0f0; }
                QListWidget::item:selected { background-color: #d0d0d0; color: #000000; } 
                QPushButton, QComboBox { background-color: #e0e0e0; color: black; border: 1px solid #aaa; padding: 0px 5px; }
                #btnAddSector { padding: 0px; padding-bottom: 4px; }
                QMenu { background-color: #ffffff; color: black; border: 1px solid #ccc; }
                QMenu::item:selected { background-color: #e0e0e0; }
                QFrame { border: 1px solid #ddd; border-radius: 4px; margin-top: 5px; }
            """)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = CtrlCVlerApp()
    ex.show()
    sys.exit(app.exec())