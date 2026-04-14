#!/usr/bin/env python3
# Test script to verify the collision editing fix for image layers

import os
import sys
from PySide6.QtWidgets import QApplication, QGraphicsView, QGraphicsScene
from PySide6.QtCore import QPointF, Qt, QEvent

# Add the project root to Python path
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

from modules.map_editor.layer_manager import LayerManager, ImageData
from modules.map_editor.collision_manager import CollisionManager
from models.map_model import MapDataModel

class TestCollisionEditFix:
    def __init__(self):
        self.test_dir = '/Users/amixc/Desktop/IDEtest/Test/test'
        self.image_path = os.path.join(self.test_dir, 'bg.png')
        self.test_map_path = '/Users/amixc/Desktop/IDEtest/Test/assets/maps/test_collision_edit'
        
        # Create test directory if it doesn't exist
        os.makedirs(self.test_map_path, exist_ok=True)
        
        # Create a mock QGraphicsView for testing
        self.view = QGraphicsView()
        self.view.setFixedSize(256, 256)
        self.scene = QGraphicsScene()
        self.view.setScene(self.scene)
        
    def test_collision_editing(self):
        print("=== Testing Collision Editing Fix ===")
        
        # Create a map model
        map_model = MapDataModel()
        map_model.map_data['width'] = 40
        map_model.map_data['height'] = 30
        map_model.map_data['tile_size'] = 16
        
        # Create layer manager
        layer_manager = LayerManager(map_model)
        
        # Create an image layer
        layer_name = "image_layer"
        image_layer = layer_manager.create_layer("image", layer_name)
        
        # Add the image to the layer
        if os.path.exists(self.image_path):
            print(f"Adding image: {self.image_path}")
            # Add image to the layer using ImageData
            image_data = ImageData(self.image_path)
            image_data.collision_enabled = True
            # Set initial collision shape
            image_data.collision_shape = {
                'points': [(0, 0), (640, 0), (640, 480), (0, 480)]
            }
            image_layer.add_image(image_data)
        else:
            print(f"Image not found: {self.image_path}")
            return
        
        # Create collision manager
        collision_manager = CollisionManager(map_model)
        collision_manager.initialize_collision_editor(self.view)
        
        # Set layer manager reference in collision manager
        class MockParentManager:
            def __init__(self, layer_manager, test_map_path):
                self.layer_manager = layer_manager
                self.current_map_path = os.path.join(test_map_path, 'test_collision_edit.info')
        
        collision_manager.parent_manager = MockParentManager(layer_manager, self.test_map_path)
        
        # Set current layer to image layer
        layer_manager.set_current_layer(0)
        
        # Set current collision image
        collision_manager.set_current_collision_image(image_layer.layer_id, 0)
        
        # Get initial collision shape
        initial_shape = image_data.collision_shape
        print(f"Initial collision shape: {initial_shape}")
        
        # Simulate mouse events to edit collision shape
        print("\nSimulating collision editing...")
        
        # Simulate mouse press on first anchor
        press_event = QEvent(QEvent.MouseButtonPress)
        press_event.setButton(Qt.LeftButton)
        press_event.setPos(self.view.mapFromScene(QPointF(-100, -100)))
        collision_manager._handle_mouse_press(press_event)
        
        # Simulate mouse move to edit collision shape
        move_event = QEvent(QEvent.MouseMove)
        move_event.setPos(self.view.mapFromScene(QPointF(-50, -50)))
        collision_manager._handle_mouse_move(move_event)
        
        # Simulate mouse release
        release_event = QEvent(QEvent.MouseButtonRelease)
        release_event.setButton(Qt.LeftButton)
        collision_manager._handle_mouse_release(release_event)
        
        # Get collision shape after edit
        after_edit_shape = image_data.collision_shape
        print(f"Collision shape after edit: {after_edit_shape}")
        
        # Check if collision shape has been edited
        if initial_shape != after_edit_shape:
            print("✅ Collision shape has been edited successfully")
        else:
            print("❌ Collision shape was not edited")
        
        # Test layer switching
        print("\nTesting layer switching...")
        
        # Create another layer
        layer_name_2 = "another_layer"
        another_layer = layer_manager.create_layer("image", layer_name_2)
        
        # Switch to the new layer
        layer_manager.set_current_layer(1)
        print("Switched to layer 2")
        
        # Switch back to the original layer
        layer_manager.set_current_layer(0)
        print("Switched back to layer 1")
        
        # Set current collision image again
        collision_manager.set_current_collision_image(image_layer.layer_id, 0)
        
        # Get collision shape after switch
        after_switch_shape = image_data.collision_shape
        print(f"Collision shape after switch: {after_switch_shape}")
        
        # Check if collision shape is the same as after edit
        if after_edit_shape == after_switch_shape:
            print("✅ Collision shape remains the same after layer switch")
        else:
            print("❌ Collision shape has changed after layer switch")
        
        # Test multiple layer switches
        print("\nTesting multiple layer switches...")
        for i in range(3):
            # Switch to layer 2
            layer_manager.set_current_layer(1)
            print(f"Switch {i+1}: Switched to layer 2")
            
            # Switch back to layer 1
            layer_manager.set_current_layer(0)
            print(f"Switch {i+1}: Switched back to layer 1")
            
            # Set current collision image
            collision_manager.set_current_collision_image(image_layer.layer_id, 0)
        
        # Get collision shape after multiple switches
        final_shape = image_data.collision_shape
        print(f"Collision shape after multiple switches: {final_shape}")
        
        # Check if collision shape is still the same
        if after_edit_shape == final_shape:
            print("✅ Collision shape remains the same after multiple layer switches")
        else:
            print("❌ Collision shape has changed after multiple layer switches")
        
        print("\n=== Test Complete ===")

if __name__ == "__main__":
    app = QApplication([])
    test = TestCollisionEditFix()
    test.test_collision_editing()
    app.quit()
