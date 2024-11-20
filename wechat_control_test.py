import uiautomation as auto
import time
from typing import Optional, List
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WeChatUIFinder:
    """微信UI元素查找器"""
    
    @staticmethod
    def find_all_possible_patterns(control, class_name: str) -> List[auto.Control]:
        """查找所有可能匹配的控件模式"""
        patterns = []
        try:
            # 1. 通过类名直接查找
            patterns.extend(control.FindAllChildren(ClassName=class_name))
            
            # 2. 通过控件类型查找
            control_type_map = {
                "Edit": auto.EditControl,
                "List": auto.ListControl,
                "Button": auto.ButtonControl,
                "Text": auto.TextControl
            }
            if class_name in control_type_map:
                patterns.extend(control.FindAllChildren(ControlType=control_type_map[class_name]))
            
            # 3. 递归查找所有子控件
            def recursive_find(parent):
                children = parent.GetChildren()
                for child in children:
                    if child.ClassName == class_name:
                        patterns.append(child)
                    recursive_find(child)
            
            recursive_find(control)
            
        except Exception as e:
            logger.error(f"查找控件模式出错: {e}")
        
        return list(set(patterns))  # 去重

    @staticmethod
    def verify_control(control, expected_attributes: dict) -> bool:
        """验证控件是否符合预期属性"""
        try:
            for attr, value in expected_attributes.items():
                if hasattr(control, attr):
                    if getattr(control, attr) != value:
                        return False
                else:
                    return False
            return True
        except Exception:
            return False

    @staticmethod
    def find_by_position(controls, position_rules: dict) -> Optional[auto.Control]:
        """通过位置规则查找控件"""
        try:
            for control in controls:
                rect = control.BoundingRectangle
                
                # 检查大小规则
                if 'min_width' in position_rules and rect.width() < position_rules['min_width']:
                    continue
                if 'min_height' in position_rules and rect.height() < position_rules['min_height']:
                    continue
                    
                # 检查位置规则
                if 'bottom_aligned' in position_rules and position_rules['bottom_aligned']:
                    parent_rect = control.GetParentControl().BoundingRectangle
                    if abs(rect.bottom - parent_rect.bottom) > 50:  # 允许50像素的误差
                        continue
                
                return control
                
        except Exception as e:
            logger.error(f"通过位置查找控件出错: {e}")
        
        return None

class WeChatControls:
    """微信控件识别类"""
    
    def __init__(self):
        self.window = None
        self.ui_finder = WeChatUIFinder()
        self.control_patterns = self._init_control_patterns()
        
    def _init_control_patterns(self) -> dict:
        """初始化控件识别模式"""
        return {
            'edit_box': {
                'class_names': ['Edit', 'TextBox', 'RichEdit'],
                'attributes': {
                    'IsEnabled': True,
                    'IsKeyboardFocusable': True
                },
                'position': {
                    'min_width': 100,
                    'min_height': 20,
                    'bottom_aligned': True
                }
            },
            'message_list': {
                'class_names': ['ListBox', 'List', 'ListView'],
                'attributes': {
                    'IsEnabled': True
                },
                'position': {
                    'min_width': 200,
                    'min_height': 300
                }
            }
            # 可以添加更多控件的识别模式
        }
    
    def init_window(self) -> bool:
        """初始化微信窗口"""
        try:
            # 尝试多个可能的窗口类名
            window_patterns = [
                {'Name': '微信', 'ClassName': 'WeChatMainWndForPC'},
                {'Name': 'WeChat', 'ClassName': 'WeChatMainWndForPC'},
                {'ClassName': 'WeChatMainWndForPC'}
            ]
            
            for pattern in window_patterns:
                self.window = auto.WindowControl(**pattern)
                if self.window.Exists():
                    logger.info("找到微信窗口")
                    return True
            
            logger.error("未找到微信窗口")
            return False
            
        except Exception as e:
            logger.error(f"初始化微信窗口失败: {e}")
            return False
    
    def find_control(self, control_type: str) -> Optional[auto.Control]:
        """查找指定类型的控件"""
        if not self.window or not self.window.Exists():
            logger.error("微信窗口未初始化")
            return None
            
        if control_type not in self.control_patterns:
            logger.error(f"未知的控件类型: {control_type}")
            return None
            
        pattern = self.control_patterns[control_type]
        all_possible_controls = []
        
        # 使用所有可能的类名查找控件
        for class_name in pattern['class_names']:
            controls = self.ui_finder.find_all_possible_patterns(self.window, class_name)
            all_possible_controls.extend(controls)
        
        # 通过属性过滤
        filtered_controls = [
            control for control in all_possible_controls
            if self.ui_finder.verify_control(control, pattern['attributes'])
        ]
        
        # 通过位置规则确定最终控件
        return self.ui_finder.find_by_position(filtered_controls, pattern['position'])

class WeChatEditBox:
    """微信编辑框控制类"""
    
    def __init__(self):
        self.controls = WeChatControls()
        self.edit_control = None
    
    def init(self) -> bool:
        """初始化"""
        try:
            if not self.controls.init_window():
                return False
                
            self.edit_control = self.controls.find_control('edit_box')
            return self.edit_control is not None
            
        except Exception as e:
            logger.error(f"初始化编辑框失败: {e}")
            return False
    
    def refresh_control(self) -> bool:
        """刷新控件引用"""
        try:
            new_control = self.controls.find_control('edit_box')
            if new_control and new_control.Exists():
                self.edit_control = new_control
                return True
            return False
        except Exception as e:
            logger.error(f"刷新控件失败: {e}")
            return False
    
    def send_message(self, message: str, retry_count: int = 3) -> bool:
        """发送消息"""
        for i in range(retry_count):
            try:
                if not self.edit_control or not self.edit_control.Exists():
                    if not self.refresh_control():
                        continue
                
                self.edit_control.SetFocus()
                time.sleep(0.1)
                self.edit_control.SendKeys(message)
                time.sleep(0.1)
                auto.Keys.Enter.send()
                return True
                
            except Exception as e:
                logger.error(f"发送消息失败 (尝试 {i+1}/{retry_count}): {e}")
                time.sleep(1)
        
        return False

def test_ui_update_handling():
    """测试UI更新处理"""
    edit_box = WeChatEditBox()
    
    if not edit_box.init():
        logger.error("初始化失败")
        return
    
    logger.info("开始测试消息发送...")
    
    # 测试发送消息
    test_messages = ["测试消息1", "测试消息2"]
    for msg in test_messages:
        if edit_box.send_message(msg):
            logger.info(f"消息发送成功: {msg}")
        else:
            logger.error(f"消息发送失败: {msg}")
        time.sleep(1)
    
    # 模拟UI更新后的处理
    logger.info("模拟UI更新...")
    if edit_box.refresh_control():
        logger.info("控件刷新成功")
        if edit_box.send_message("UI更新后的测试消息"):
            logger.info("UI更新后消息发送成功")
        else:
            logger.error("UI更新后消息发送失败")
    else:
        logger.error("控件刷新失败")

if __name__ == "__main__":
    test_ui_update_handling()