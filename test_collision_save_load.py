#!/usr/bin/env python3
# Test script to verify collision save/load functionality for image layers

import os
import sys
from PySide6.QtWidgets import QApplication, QGraphicsView, QGraphicsScene
from PySide6.QtCore import QPointF

# Add the project root to Python path
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

from modules.map_editor.layer_manager import LayerManager, ImageData
from modules.map_editor.collision_manager import CollisionManager
from models.map_model import MapDataModel

class TestCollisionSaveLoad:
    def __init__(self):
        self.test_dir = '/Users/amixc/Desktop/IDEtest/Test/test'
        self.image_path = os.path.join(self.test_dir, 'bg.png')
        self.test_map_path = '/Users/amixc/Desktop/IDEtest/Test/assets/maps/test_collision_save_load'
        
        # Create test directory if it doesn't exist
        os.makedirs(self.test_map_path, exist_ok=True)
        
        # Create a mock QGraphicsView for testing
        self.view = QGraphicsView()
        self.view.setFixedSize(256, 256)
        self.scene = QGraphicsScene()
        self.view.setScene(self.scene)
        
    def test_collision_save_load(self):
        print("=== Testing Collision Save/Load Fix ===")
        
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
                self.current_map_path = os.path.join(test_map_path, 'test_collision_save_load.info')
        
        collision_manager.parent_manager = MockParentManager(layer_manager, self.test_map_path)
        
        # Set current layer to image layer
        layer_manager.set_current_layer(0)
        
        # Set current collision image
        collision_manager.set_current_collision_image(image_layer.layer_id, 0)
        
        # Get initial collision shape
        initial_shape = image_data.collision_shape
        print(f"Initial collision shape: {initial_shape}")
        
        # Simulate collision editing by directly modifying collision_points
        print("\nSimulating collision editing...")
        
        # Manually set collision points to simulate editing
        collision_manager.collision_points = [
            QPointF(50, 50),    # Modified top-left corner
            QPointF(590, 0),    # Top-right corner
            QPointF(640, 430),  # Bottom-right corner
            QPointF(0, 480)     # Bottom-left corner
        ]
        
        # Test the save logic directly
        print("Testing collision save logic...")
        
        # Get the image data
        image_data = image_layer.images[0]
        
        # Calculate scale and save (simulating what happens in mouse release)
        display_to_original_scale = 1.0
        if collision_manager.tile_item:
            # Get original image size
            pixmap = image_data.pixmap
            if pixmap and not pixmap.isNull():
                original_width = pixmap.width()
                original_height = pixmap.height()
                # Get display image size
                display_width = collision_manager.tile_item.boundingRect().width()
                display_height = collision_manager.tile_item.boundingRect().height()
                # Calculate scale
                if display_width > 0:
                    display_to_original_scale = original_width / display_width
                elif display_height > 0:
                    display_to_original_scale = original_height / display_height
                print(f"Save scale: {display_to_original_scale}")
        
        # Convert collision points to original scale
        points_data = [
            [p.x() * display_to_original_scale, p.y() * display_to_original_scale]
            for p in collision_manager.collision_points
        ]
        
        # Save to image data
        image_data.collision_shape = {"points": points_data}
        print(f"Saved collision shape: {image_data.collision_shape}")
        
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
        
        # Set current collision image again (this will reload the collision shape)
        collision_manager.set_current_collision_image(image_layer.layer_id, 0)
        
        # Get collision shape after switch
        after_switch_shape = image_data.collision_shape
        print(f"Collision shape after switch: {after_switch_shape}")
        
        # Check if collision shape is preserved
        if points_data == after_switch_shape['points']:
            print("✅ Collision shape is preserved after layer switch")
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
        if points_data == final_shape['points']:
            print("✅ Collision shape remains the same after multiple layer switches")
        else:
            print("❌ Collision shape has changed after multiple layer switches")
        
        print("\n=== Test Complete ===")

if __name__ == "__main__":
    app = QApplication([])
    test = TestCollisionSaveLoad()
    test.test_collision_save_load()
    app.quit()
