#!/usr/bin/env python3
# Test script to verify the collision scaling fix

import os
import sys
from PySide6.QtWidgets import QApplication, QGraphicsView, QGraphicsScene

# Add the project root to Python path
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

from modules.map_editor.layer_manager import LayerManager, ImageData
from modules.map_editor.collision_manager import CollisionManager
from models.map_model import MapDataModel

class TestCollisionFix:
    def __init__(self):
        self.test_dir = '/Users/amixc/Desktop/IDEtest/Test/test'
        self.image_path = os.path.join(self.test_dir, 'bg.png')
        self.test_map_path = '/Users/amixc/Desktop/IDEtest/Test/assets/maps/test_collision_fix'
        
        # Create test directory if it doesn't exist
        os.makedirs(self.test_map_path, exist_ok=True)
        
        # Create a mock QGraphicsView for testing
        self.view = QGraphicsView()
        self.view.setFixedSize(256, 256)
        self.scene = QGraphicsScene()
        self.view.setScene(self.scene)
        
    def test_collision_scaling_fix(self):
        print("=== Testing Collision Scaling Fix ===")
        
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
            def __init__(self, layer_manager):
                self.layer_manager = layer_manager
        
        collision_manager.parent_manager = MockParentManager(layer_manager)
        
        # Set current layer to image layer
        layer_manager.set_current_layer(0)
        
        # Set current collision image
        collision_manager.set_current_collision_image(image_layer.layer_id, 0)
        
        # Test collision shape scaling by simulating layer switching
        print("\nTesting collision shape scaling...")
        
        # Get initial collision shape
        initial_shape = image_data.collision_shape
        print(f"Initial collision shape: {initial_shape}")
        
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
        
        # Check if collision shape has changed
        if initial_shape == after_switch_shape:
            print("✅ Collision shape remains the same after layer switch")
        else:
            print("❌ Collision shape has changed after layer switch")
        
        # Test multiple layer switches
        print("\nTesting multiple layer switches...")
        for i in range(5):
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
        
        # Check if collision shape has changed
        if initial_shape == final_shape:
            print("✅ Collision shape remains the same after multiple layer switches")
        else:
            print("❌ Collision shape has changed after multiple layer switches")
        
        # Test the _update_collision_display method
        print("\nTesting _update_collision_display method...")
        try:
            collision_manager._update_collision_display()
            print("✅ _update_collision_display executed successfully")
        except Exception as e:
            print(f"❌ Error in _update_collision_display: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n=== Test Complete ===")

if __name__ == "__main__":
    app = QApplication([])
    test = TestCollisionFix()
    test.test_collision_scaling_fix()
    app.quit()
