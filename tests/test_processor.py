import unittest

import numpy as np

from src.processor import (
    create_border_grow_mask,
    center_foreground_on_canvas,
    create_binary_mask,
    create_watershed_mask,
    process_image_array,
    refine_mask_with_main_contour,
)


class TestProcessor(unittest.TestCase):
    def test_empty_foreground_returns_green_canvas(self):
        image = np.zeros((4, 4, 3), dtype=np.uint8)
        mask = np.zeros((4, 4), dtype=np.uint8)
        out = center_foreground_on_canvas(image, mask, target_width=6, target_height=5)
        self.assertEqual(out.shape, (5, 6, 3))
        self.assertTrue(np.all(out == np.array([0, 255, 0], dtype=np.uint8)))

    def test_create_binary_mask_respects_threshold(self):
        gray = np.array([[10, 200], [251, 255]], dtype=np.uint8)
        mask = create_binary_mask(gray, threshold=250)
        expected = np.array([[0, 0], [255, 255]], dtype=np.uint8)
        self.assertTrue(np.array_equal(mask, expected))

    def test_large_foreground_is_center_cropped(self):
        image = np.full((8, 8, 3), 255, dtype=np.uint8)
        out = process_image_array(
            img_color=image,
            threshold=1,
            target_width=4,
            target_height=4,
        )
        self.assertEqual(out.shape, (4, 4, 3))
        self.assertTrue(np.all(out == 255))

    def test_refine_mask_keeps_main_contour(self):
        mask = np.zeros((20, 20), dtype=np.uint8)
        mask[2:5, 2:5] = 255  # small noisy island
        mask[8:18, 8:18] = 255  # main object
        refined = refine_mask_with_main_contour(mask, morph_kernel_size=3)
        self.assertEqual(refined[3, 3], 0)
        self.assertEqual(refined[10, 10], 255)

    def test_contour_mode_turns_outside_into_green(self):
        image = np.zeros((10, 10, 3), dtype=np.uint8)
        image[3:7, 3:7] = [255, 255, 255]
        out = process_image_array(
            img_color=image,
            threshold=20,
            target_width=10,
            target_height=10,
            refine_method="contour",
            morph_kernel_size=3,
        )
        self.assertTrue(np.array_equal(out[0, 0], np.array([0, 255, 0], dtype=np.uint8)))
        self.assertTrue(np.array_equal(out[5, 5], np.array([255, 255, 255], dtype=np.uint8)))

    def test_watershed_keeps_dark_ring_against_mid_background(self):
        image = np.full((30, 30, 3), 160, dtype=np.uint8)
        image[9:21, 9:21] = [92, 92, 92]
        image[12:18, 12:18] = [250, 250, 250]
        gray = image[:, :, 0]
        mask = create_watershed_mask(image, gray, threshold=240, bg_tolerance=10)
        self.assertEqual(mask[15, 15], 255)  # bright core
        self.assertEqual(mask[10, 10], 255)  # dark ring should be kept
        self.assertEqual(mask[2, 2], 0)  # background

    def test_border_grow_keeps_dark_ring_against_bright_background(self):
        gray = np.full((24, 24), 160, dtype=np.uint8)
        gray[7:17, 7:17] = 92
        gray[10:14, 10:14] = 250
        mask = create_border_grow_mask(gray, background_threshold=110)
        self.assertEqual(mask[1, 1], 0)
        self.assertEqual(mask[8, 8], 255)
        self.assertEqual(mask[12, 12], 255)

if __name__ == "__main__":
    unittest.main()
