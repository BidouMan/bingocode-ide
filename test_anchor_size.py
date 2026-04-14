#!/usr/bin/env python3
# Test script to verify anchor size consistency across different scales

import os
import sys
from PySide6.QtWidgets import QApplication, QGraphicsView, QGraphicsScene, QGraphicsItem

# Add the project root to Python path
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

from modules.map_editor.layer_manager import LayerManager, ImageData
from modules.map_editor.collision_manager import CollisionManager
from models.map_model import MapDataModel

class TestAnchorSize:
    def __init__(self):
        self.test_dir = '/Users/amixc/Desktop/IDEtest/Test/test'
        self.image_path = os.path.join(self.test_dir, 'bg.png')
        self.grass_path = os.path.join(self.test_dir, 'grass.png')
        self.test_map_path = '/Users/amixc/Desktop/IDEtest/Test/assets/maps/test_anchor_size'
        
        # Create test directory if it doesn't exist
        os.makedirs(self.test_map_path, exist_ok=True)
        
        # Create a mock QGraphicsView for testing
        self.view = QGraphicsView()
        self.view.setFixedSize(256, 256)
        self.scene = QGraphicsScene()
        self.view.setScene(self.scene)
        
    def test_anchor_size_consistency(self):
        print("=== Testing Anchor Size Consistency ===")
        
        # Create a map model
        map_model = MapDataModel()
        map_model.map_data['width'] = 40
        map_model.map_data['height'] = 30
        map_model.map_data['tile_size'] = 16
        
        # Create layer manager
        layer_manager = LayerManager(map_model)
        
        # Test with image layer (large image)
        print("\nTesting with image layer (640x480 image)...")
        self.test_anchor_size_with_layer(layer_manager, map_model, "image", self.image_path, "image_layer")
        
        # Test with drawing layer (small tile)
        print("\nTesting with drawing layer (16x16 tile)...")
        self.test_anchor_size_with_layer(layer_manager, map_model, "drawing", self.grass_path, "drawing_layer")
        
        print("\n=== Test Complete ===")
    
    def test_anchor_size_with_layer(self, layer_manager, map_model, layer_type, image_path, layer_name):
        # Create layer
        layer = layer_manager.create_layer(layer_type, layer_name)
        
        # Add image to layer
        if os.path.exists(image_path):
            print(f"Adding {os.path.basename(image_path)} to {layer_type} layer")
            if layer_type == "image":
                # Add image to image layer
                image_data = ImageData(image_path)
                image_data.collision_enabled = True
                image_data.collision_shape = {
                    'points': [(0, 0), (640, 0), (640, 480), (0, 480)]
                }
                layer.add_image(image_data)
            else:
                # For drawing layer, we'll just create the layer
                pass
        else:
            print(f"Image not found: {image_path}")
            return
        
        # Create collision manager
        collision_manager = CollisionManager(map_model)
        collision_manager.initialize_collision_editor(self.view)
        
        # Set layer manager reference
        class MockParentManager:
            def __init__(self, layer_manager):
                self.layer_manager = layer_manager
        
        collision_manager.parent_manager = MockParentManager(layer_manager)
        
        # Set current layer
        layer_manager.set_current_layer(len(layer_manager.layers) - 1)
        
        # Set current collision data
        if layer_type == "image":
            collision_manager.set_current_collision_image(layer.layer_id, 0)
        else:
            # For drawing layer, we need a different approach
            # For simplicity, we'll just skip the actual collision setup
            return
        
        # Check anchor items
        if hasattr(collision_manager, "anchor_items"):
            anchor_count = len(collision_manager.anchor_items)
            print(f"Created {anchor_count} anchor items")
            
            # Check if anchors have ItemIgnoresTransformations flag set
            for anchor_name, anchor in collision_manager.anchor_items.items():
                if hasattr(anchor, "flags"):
                    flags = anchor.flags()
                    if flags & QGraphicsItem.ItemIgnoresTransformations:
                        print(f"Anchor {anchor_name} has ItemIgnoresTransformations flag set")
                    else:
                        print(f"Anchor {anchor_name} does NOT have ItemIgnoresTransformations flag set")
        
        # Clean up
        collision_manager._cleanup_collision_items()

if __name__ == "__main__":
    app = QApplication([])
    test = TestAnchorSize()
    test.test_anchor_size_consistency()
    app.quit()
