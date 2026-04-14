#!/usr/bin/env python3
# Test script to reproduce the collision scaling issue in image layers

import os
import sys
import json
from PySide6.QtWidgets import QApplication, QGraphicsView, QGraphicsScene
from PySide6.QtCore import Qt

# Add the project root to Python path
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

from modules.map_editor.layer_manager import LayerManager, ImageLayer, ImageData
from modules.map_editor.collision_manager import CollisionManager
from models.map_model import MapDataModel

class TestCollisionScaling:
    def __init__(self):
        self.test_dir = '/Users/amixc/Desktop/IDEtest/Test/test'
        self.image_path = os.path.join(self.test_dir, 'bg.png')
        self.test_map_path = '/Users/amixc/Desktop/IDEtest/Test/assets/maps/test_collision'
        
        # Create test directory if it doesn't exist
        os.makedirs(self.test_map_path, exist_ok=True)
        
        # Create a mock QGraphicsView for testing
        self.view = QGraphicsView()
        self.view.setFixedSize(256, 256)
        self.scene = QGraphicsScene()
        self.view.setScene(self.scene)
        
    def test_collision_scaling(self):
        print("=== Testing Collision Scaling Issue ===")
        
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
            image_data.collision_shape = {
                'points': [(0, 0), (640, 0), (640, 480), (0, 480)]
            }
            image_layer.add_image(image_data)
        else:
            print(f"Image not found: {self.image_path}")
            return
        
        # Create collision manager
        collision_manager = CollisionManager(None, self.view, None)
        collision_manager.layer_manager = layer_manager
        
        # Set current layer to image layer
        layer_manager.current_layer_index = 0
        
        # Test collision shape scaling
        print("\nTesting collision shape scaling...")
        
        # Simulate layer switching
        print("Simulating layer switch...")
        
        # Create another layer
        layer_name_2 = "another_layer"
        another_layer = layer_manager.create_layer("image", layer_name_2)
        
        # Switch to the new layer
        layer_manager.set_current_layer(1)
        print("Switched to layer 2")
        
        # Switch back to the original layer
        layer_manager.set_current_layer(0)
        print("Switched back to layer 1")
        
        # Check collision shape after switch
        print("\nChecking collision shape after switch...")
        if image_layer.images:
            collision_shape = image_layer.images[0].get('collision_shape')
            if collision_shape:
                print(f"Collision shape points: {collision_shape['points']}")
                # Check if points are scaled incorrectly
                min_x = min(p[0] for p in collision_shape['points'])
                max_x = max(p[0] for p in collision_shape['points'])
                min_y = min(p[1] for p in collision_shape['points'])
                max_y = max(p[1] for p in collision_shape['points'])
                print(f"Collision shape bounds: x[{min_x}, {max_x}], y[{min_y}, {max_y}]")
                print(f"Expected bounds: x[0, 640], y[0, 480]")
                
                # Check if scaling issue occurred
                if max_x < 640 or max_y < 480:
                    print("❌ Collision shape has been scaled down!")
                else:
                    print("✅ Collision shape bounds are correct")
        
        # Test the _update_collision_display method directly
        print("\nTesting _update_collision_display method...")
        try:
            # Set up the collision manager for testing
            collision_manager.current_tile_set_index = 0
            collision_manager.current_tile_index = 0
            
            # Call the method to update collision display
            collision_manager._update_collision_display()
            print("✅ _update_collision_display executed successfully")
            
            # Check the scene items
            items = self.scene.items()
            print(f"Number of items in scene: {len(items)}")
            for i, item in enumerate(items):
                print(f"Item {i}: {type(item).__name__}, pos: {item.pos()}, scale: {item.scale()}")
                
        except Exception as e:
            print(f"❌ Error in _update_collision_display: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n=== Test Complete ===")

if __name__ == "__main__":
    app = QApplication([])
    test = TestCollisionScaling()
    test.test_collision_scaling()
    app.quit()
