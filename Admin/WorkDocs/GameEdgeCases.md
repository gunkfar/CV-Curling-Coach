# Curling CV Detection - Edge Cases Document

This document outlines known edge cases in the curling computer vision (CV) detection pipeline. These scenarios present unique challenge conditions where default visual tracking or game-state detection logic may fail.

| Edge Case Name | Edge Case Description | Solved? |
| :--- | :--- | :--- |
| **Two Hogged Stones** | Two consecutive curling stones fail to cross the hog line and are removed from play before entering the active camera detection frame. This can cause consecutive frame skips or missing stone index counts in the tracking sequence. | No |
| **Same-Color Replacement Knockout** | A stone collides with a stationary stone of the same color, knocking the original stone completely out of the camera frame while the striking stone comes to rest in the exact position of the removed stone. This makes the positional shift look seamless and can cause the system to fail to register that a new stone was introduced. | No |

