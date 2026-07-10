"""
DetaBeta engines package.

Each engine is a pure-Python module that answers one question about the data.
They contain NO web framework code -- they take data in and return structured
results out, so they can be tested in isolation and reused anywhere.

Engines (built incrementally):
    1. dataset_understanding  -- "What kind of data is this?"          [DONE]
    2. data_health            -- "Can I trust this dataset?"           [next]
    3. investigation          -- "What interesting things exist?"
    4. statistics             -- "Are these findings meaningful?"
    5. feature_lab            -- "How can this data be improved?"
    6. ml_recommendation      -- "What should I model, and how?"
    7. experiment_studio      -- "Which model performs best?"
    8. explainability         -- "Why did the model predict this?"
    9. report                 -- "What should another human learn?"
"""
