"""
The reasoning logic for Engine 6 (ML Recommendation).

Split into four focused steps, each a pure function so it is easy to test and
easy to read:

  detect_problem_type(...)  -> classification vs regression, with reasoning
  select_features(...)      -> which columns to model on, and which to drop
  recommend_algorithms(...) -> ranked algorithms with evidence
  plan_validation(...)      -> how to evaluate honestly

None of these touch scikit-learn. They only reason over Engine 1's profiles.
"""

from __future__ import annotations

from ..dataset_understanding.types import (
    ColumnProfile,
    DatasetProfile,
    SemanticType,
)
from .types import (
    AlgorithmSuggestion,
    Complexity,
    ProblemType,
    ValidationPlan,
)

# Semantic types that make good model inputs as-is.
_MODELLABLE = {
    SemanticType.NUMERIC_CONTINUOUS,
    SemanticType.NUMERIC_DISCRETE,
    SemanticType.BINARY,
    SemanticType.CATEGORICAL,
    SemanticType.DATETIME,
}


# --------------------------------------------------------------------------- #
# Step 1: What kind of problem is this?
# --------------------------------------------------------------------------- #
def detect_problem_type(
    target: ColumnProfile,
) -> tuple[ProblemType, list[str]]:
    """
    Decide the supervised-learning problem type from the TARGET column alone.

    The key data-science idea: the *target's* nature defines the problem.
      - a numeric, continuous target  -> regression
      - a two-value target            -> binary classification
      - a small-set categorical target-> multiclass classification
    """
    reasoning: list[str] = []
    st = target.semantic_type

    if st == SemanticType.BINARY:
        reasoning.append(
            f"Target '{target.name}' has exactly 2 distinct values, so this is "
            "a binary classification problem (predict one of two classes)."
        )
        return ProblemType.BINARY_CLASSIFICATION, reasoning

    if st == SemanticType.NUMERIC_CONTINUOUS:
        reasoning.append(
            f"Target '{target.name}' is a continuous number, so this is a "
            "regression problem (predict a quantity)."
        )
        return ProblemType.REGRESSION, reasoning

    if st == SemanticType.CATEGORICAL:
        reasoning.append(
            f"Target '{target.name}' has {target.n_unique} unordered categories, "
            "so this is a multiclass classification problem."
        )
        return ProblemType.MULTICLASS_CLASSIFICATION, reasoning

    if st == SemanticType.NUMERIC_DISCRETE:
        # Discrete numbers are ambiguous: few distinct values behave like classes,
        # many distinct values behave like a quantity. We reason it out.
        if target.n_unique <= 15:
            reasoning.append(
                f"Target '{target.name}' is a discrete number with only "
                f"{target.n_unique} distinct values, so we treat it as multiclass "
                "classification. (If these values are truly ordered quantities, "
                "regression may fit better -- you can override this.)"
            )
            return ProblemType.MULTICLASS_CLASSIFICATION, reasoning
        reasoning.append(
            f"Target '{target.name}' is a discrete number with many distinct "
            f"values ({target.n_unique}), so we treat it as regression."
        )
        return ProblemType.REGRESSION, reasoning

    # Identifiers, text, constants, unknown -> not a usable target.
    reasoning.append(
        f"Target '{target.name}' is of type '{st.value}', which is not a usable "
        "prediction target. Choose a binary, categorical, or numeric column."
    )
    return ProblemType.UNKNOWN, reasoning


# --------------------------------------------------------------------------- #
# Step 2: Which columns should the model actually use?
# --------------------------------------------------------------------------- #
def select_features(
    profile: DatasetProfile,
    target_name: str,
) -> tuple[list[str], dict[str, str]]:
    """
    Decide which columns become model inputs, and record WHY others are dropped.

    Excluding the wrong columns is critical:
      - identifiers cause data leakage / memorisation
      - constants carry no information
      - free text needs NLP we are not doing here
      - very-high-missing columns are unreliable
    """
    features: list[str] = []
    excluded: dict[str, str] = {}

    for col in profile.columns:
        if col.name == target_name:
            continue  # never feed the answer to itself

        st = col.semantic_type

        if st == SemanticType.IDENTIFIER:
            excluded[col.name] = (
                "Identifier column -- unique per row, would cause the model to "
                "memorise rows (data leakage) instead of learning patterns."
            )
            continue
        if st == SemanticType.CONSTANT:
            excluded[col.name] = "Constant column -- same value everywhere, zero information."
            continue
        if st == SemanticType.TEXT:
            excluded[col.name] = (
                "Free-text column -- needs NLP feature extraction before it can "
                "be modelled; excluded from the standard tabular pipeline."
            )
            continue
        if st == SemanticType.UNKNOWN:
            excluded[col.name] = "Type could not be determined confidently; excluded to be safe."
            continue
        if col.missing_pct > 60.0:
            excluded[col.name] = (
                f"{col.missing_pct:.0f}% of values are missing -- too unreliable "
                "to use as a feature."
            )
            continue

        if st in _MODELLABLE:
            features.append(col.name)
        else:
            excluded[col.name] = f"Type '{st.value}' is not used as a direct model input."

    return features, excluded


# --------------------------------------------------------------------------- #
# Step 3: Which algorithms should we try?
# --------------------------------------------------------------------------- #
def recommend_algorithms(
    problem_type: ProblemType,
    n_rows: int,
    n_features: int,
) -> list[AlgorithmSuggestion]:
    """
    Recommend a ranked list of algorithms for the detected problem type.

    Philosophy: ALWAYS start from a simple, interpretable baseline, then offer
    more powerful models that must "earn" their extra complexity. We also adapt
    to dataset size -- advanced models need enough rows to shine.
    """
    algos: list[AlgorithmSuggestion] = []
    is_classification = problem_type in (
        ProblemType.BINARY_CLASSIFICATION,
        ProblemType.MULTICLASS_CLASSIFICATION,
    )

    if problem_type == ProblemType.UNKNOWN:
        return algos

    if is_classification:
        algos.append(
            AlgorithmSuggestion(
                name="Logistic Regression",
                rank=1,
                complexity=Complexity.SIMPLE,
                is_baseline=True,
                sklearn_path="sklearn.linear_model.LogisticRegression",
                reasoning=[
                    "A simple, fast, interpretable baseline for classification.",
                    "Its coefficients show each feature's direction and strength, "
                    "so you can explain predictions.",
                ],
                pros=["Very interpretable", "Fast to train", "Hard to overfit"],
                cons=["Assumes roughly linear decision boundaries"],
            )
        )
        algos.append(
            AlgorithmSuggestion(
                name="Decision Tree",
                rank=2,
                complexity=Complexity.SIMPLE,
                sklearn_path="sklearn.tree.DecisionTreeClassifier",
                reasoning=[
                    "Captures non-linear splits and is easy to visualise.",
                    "No feature scaling required.",
                ],
                pros=["Human-readable rules", "Handles non-linearity"],
                cons=["Overfits easily if not depth-limited"],
            )
        )
        algos.append(
            AlgorithmSuggestion(
                name="Random Forest",
                rank=3,
                complexity=Complexity.MODERATE,
                sklearn_path="sklearn.ensemble.RandomForestClassifier",
                reasoning=[
                    "An ensemble of trees -- usually strong accuracy with little tuning.",
                    "Provides feature-importance scores for explainability.",
                ],
                pros=["Strong default accuracy", "Robust to outliers", "Feature importances"],
                cons=["Less interpretable than a single tree", "Larger model"],
            )
        )
    else:  # regression
        algos.append(
            AlgorithmSuggestion(
                name="Linear Regression",
                rank=1,
                complexity=Complexity.SIMPLE,
                is_baseline=True,
                sklearn_path="sklearn.linear_model.LinearRegression",
                reasoning=[
                    "The natural interpretable baseline for predicting a quantity.",
                    "Coefficients tell you how each feature moves the prediction.",
                ],
                pros=["Very interpretable", "Fast", "Well-understood"],
                cons=["Assumes a linear relationship", "Sensitive to outliers"],
            )
        )
        algos.append(
            AlgorithmSuggestion(
                name="Decision Tree Regressor",
                rank=2,
                complexity=Complexity.SIMPLE,
                sklearn_path="sklearn.tree.DecisionTreeRegressor",
                reasoning=[
                    "Captures non-linear relationships without scaling.",
                ],
                pros=["Handles non-linearity", "No scaling needed"],
                cons=["Overfits without depth limits"],
            )
        )
        algos.append(
            AlgorithmSuggestion(
                name="Random Forest Regressor",
                rank=3,
                complexity=Complexity.MODERATE,
                sklearn_path="sklearn.ensemble.RandomForestRegressor",
                reasoning=[
                    "Ensemble of trees -- strong accuracy with minimal tuning.",
                    "Reports feature importances.",
                ],
                pros=["Strong default accuracy", "Robust", "Feature importances"],
                cons=["Less interpretable", "Larger model"],
            )
        )

    # Adapt to dataset size: gradient boosting shines on larger data.
    if n_rows >= 500:
        boost_name = (
            "Gradient Boosting" if is_classification else "Gradient Boosting Regressor"
        )
        boost_path = (
            "sklearn.ensemble.GradientBoostingClassifier"
            if is_classification
            else "sklearn.ensemble.GradientBoostingRegressor"
        )
        algos.append(
            AlgorithmSuggestion(
                name=boost_name,
                rank=4,
                complexity=Complexity.ADVANCED,
                sklearn_path=boost_path,
                reasoning=[
                    f"You have {n_rows} rows -- enough data for a boosting model "
                    "to often deliver top accuracy.",
                    "Builds trees sequentially, each correcting the previous errors.",
                ],
                pros=["Often best-in-class accuracy"],
                cons=["Slower to train", "More hyperparameters", "Harder to interpret"],
            )
        )
    else:
        # Not an algorithm, but an important teaching note appended to rank-3 model.
        algos[-1].cons.append(
            f"With only {n_rows} rows, advanced models (e.g. gradient boosting) "
            "are likely to overfit -- prefer the simpler options above."
        )

    return algos


# --------------------------------------------------------------------------- #
# Step 4: How should we validate?
# --------------------------------------------------------------------------- #
def plan_validation(
    problem_type: ProblemType,
    n_rows: int,
    target: ColumnProfile,
) -> ValidationPlan:
    """
    Recommend an honest evaluation strategy and the right primary metric.

    Two teaching points baked in:
      - always hold out data the model never saw (cross-validation)
      - accuracy is misleading on imbalanced classes -> prefer F1 / ROC-AUC
    """
    is_classification = problem_type in (
        ProblemType.BINARY_CLASSIFICATION,
        ProblemType.MULTICLASS_CLASSIFICATION,
    )
    reasoning: list[str] = []

    # Small datasets benefit most from cross-validation (every row gets used
    # for both training and testing across folds).
    use_cv = n_rows < 10000
    n_folds = 5

    if is_classification:
        stratify = True
        reasoning.append(
            "Using stratified folds so each fold keeps the same class balance as "
            "the full dataset -- otherwise a fold could miss a class entirely."
        )

        # Detect imbalance from the target's top value share, if available.
        top_values = target.stats.get("top_values") or {}
        imbalanced = False
        if top_values and target.n_total:
            top_share = max(top_values.values()) / target.n_total
            imbalanced = top_share >= 0.7

        if imbalanced:
            primary = "f1"
            others = ["roc_auc", "precision", "recall", "accuracy"]
            reasoning.append(
                "The target looks imbalanced, so accuracy would be misleading "
                "(a model can score high by always predicting the majority class). "
                "We optimise F1, which balances precision and recall."
            )
        else:
            primary = "accuracy"
            others = ["f1", "roc_auc", "precision", "recall"]
            reasoning.append(
                "Classes look reasonably balanced, so accuracy is a fair primary "
                "metric; we still report F1 and ROC-AUC as a cross-check."
            )
    else:
        stratify = False
        primary = "rmse"
        others = ["mae", "r2"]
        reasoning.append(
            "For regression we optimise RMSE (penalises large errors) and also "
            "report MAE (average error) and R^2 (variance explained)."
        )

    if use_cv:
        strategy = f"{'Stratified ' if stratify else ''}{n_folds}-fold cross-validation"
        reasoning.append(
            f"With {n_rows} rows, {n_folds}-fold cross-validation gives a more "
            "reliable score than a single split by testing on every row once."
        )
    else:
        strategy = "Hold-out train/test split (80/20)"
        reasoning.append(
            f"With {n_rows} rows, a single 80/20 split is fast and statistically "
            "sufficient; cross-validation would add cost for little gain."
        )

    return ValidationPlan(
        strategy=strategy,
        test_size=0.2,
        n_folds=n_folds,
        stratify=stratify,
        primary_metric=primary,
        other_metrics=others,
        reasoning=reasoning,
    )
