"""
AI Recipe Recommendation System
--------------------------------
A Streamlit app that recommends recipes based on the ingredients you have,
how many people you're cooking for, your time limit, and any allergies.

Recipes are ranked by an ingredient match score (how much of each recipe you
can already make with what you have), and quantities are scaled to your serving
size. Allergen ingredients are flagged with suggested substitutions.
"""

import streamlit as st
import pandas as pd
import re

# ---------------------------------------------------------------------------
# Allergy substitution dictionary
# ---------------------------------------------------------------------------
substitute_dict = {
    "milk": "plant-based milk (almond, soy, oat)",
    "egg": "chia seed gel or mashed banana",
    "butter": "olive oil or plant-based margarine",
    "cheese": "nutritional yeast or vegan cheese",
    "nuts": "sunflower seeds or pumpkin seeds",
    "peanut": "sunflower seed butter",
    "shrimp": "tofu or tempeh",
    "fish": "tofu, jackfruit, or seitan",
    "salmon": "marinated tofu",
    "flour": "gluten-free flour or almond flour",
    "soy": "coconut aminos",
    "soy sauce": "coconut aminos",
    "yogurt": "coconut yogurt or soy yogurt",
    "paneer": "firm tofu",
    "feta": "vegan feta or crumbled tofu",
}

# ---------------------------------------------------------------------------
# Load dataset (cached so it only reads from disk once)
# ---------------------------------------------------------------------------
@st.cache_data
def load_data(path="recipes.csv"):
    df = pd.read_csv(path)
    # Normalise text columns once, up front, so matching is reliable.
    df["ingredients"] = df["ingredients"].fillna("").str.lower()
    df["title"] = df["title"].fillna("Untitled")
    return df


recipes = load_data()

# ---------------------------------------------------------------------------
# Helper: split a recipe's ingredient string into a clean set of items
# ---------------------------------------------------------------------------
def ingredient_set(ingredients_text):
    """'chicken, rice, garlic' -> {'chicken', 'rice', 'garlic'}"""
    return {item.strip() for item in ingredients_text.split(",") if item.strip()}


# ---------------------------------------------------------------------------
# Core matching logic: score how well the user's ingredients cover a recipe
# ---------------------------------------------------------------------------
def match_score(user_ingredients, recipe_ingredients_text):
    """
    Returns a score from 0 to 1 = (how many of the recipe's ingredients the
    user has) / (total ingredients in the recipe).

    Example: recipe needs {chicken, rice, garlic, salt}; user has
    {chicken, rice}. Score = 2/4 = 0.5 (50% match).
    """
    recipe_ings = ingredient_set(recipe_ingredients_text)
    if not recipe_ings:
        return 0.0

    have = 0
    for recipe_ing in recipe_ings:
        # A user ingredient "chicken" should match recipe "chicken breast",
        # so we check whether the user's word appears within the recipe item.
        if any(user_ing in recipe_ing or recipe_ing in user_ing
               for user_ing in user_ingredients):
            have += 1

    return have / len(recipe_ings)


# ---------------------------------------------------------------------------
# Ingredient quantity scaling (scales the detailed ingredient_list)
# ---------------------------------------------------------------------------
def scale_ingredients(ingredient_list, original_servings, target_servings):
    if original_servings <= 0:
        original_servings = 1
    scaled = []
    for item in str(ingredient_list).split(";"):
        item = item.strip()
        if not item:
            continue
        match = re.match(r"(\d*\.?\d+)\s*([a-zA-Z]+)?\s+(.*)", item)
        if match:
            qty = float(match.group(1))
            unit = match.group(2) or ""
            name = match.group(3)
            new_qty = round(qty * target_servings / original_servings, 2)
            # drop a trailing .0 so we show "3" not "3.0"
            new_qty = int(new_qty) if new_qty == int(new_qty) else new_qty
            scaled.append(f"{new_qty} {unit} {name}".strip())
        else:
            scaled.append(item)  # keep as-is if there's no leading quantity
    return scaled


# ---------------------------------------------------------------------------
# Recommendation: filter by time/allergies, score, sort by best match
# ---------------------------------------------------------------------------
def recommend(user_ingredients, df, time_limit, allergies, min_match=0.0):
    results = []
    for _, row in df.iterrows():
        # Hard filters first: skip recipes over the time budget...
        if row["time_minutes"] > time_limit:
            continue
        # ...or that contain an allergen the user listed.
        if any(allergen in row["ingredients"] for allergen in allergies):
            continue

        score = match_score(user_ingredients, row["ingredients"])
        if score > min_match:
            results.append((score, row))

    # Sort by score, highest first.
    results.sort(key=lambda pair: pair[0], reverse=True)
    return results


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
st.set_page_config(page_title="AI Recipe Recommender", page_icon="🍳")
st.title("🍳 AI Recipe Recommendation System")
st.caption(f"Searching {len(recipes):,} recipes across {recipes['cuisine'].nunique()} cuisines.")

user_input = st.text_input("What ingredients do you have? (e.g., chicken, rice, garlic)")
col1, col2 = st.columns(2)
with col1:
    people = st.number_input("Cooking for how many?", min_value=1, value=2)
with col2:
    time_limit = st.slider("Time available (minutes)", 5, 120, 30)

allergy_input = st.text_input("Any allergies? (e.g., milk, egg, nuts)")
allergies = [a.strip().lower() for a in allergy_input.split(",") if a.strip()]

max_results = st.slider("How many recipes to show?", 1, 20, 5)

# ---------------------------------------------------------------------------
# Run and display
# ---------------------------------------------------------------------------
if user_input:
    user_ingredients = [i.strip().lower() for i in user_input.split(",") if i.strip()]
    matches = recommend(user_ingredients, recipes, time_limit, allergies)

    if matches:
        st.subheader(f"Top {min(max_results, len(matches))} matches")
        for score, row in matches[:max_results]:
            st.markdown(f"### {row['title']}")
            st.progress(score, text=f"Ingredient match: {score*100:.0f}%")
            st.markdown(
                f"**Cuisine:** {row['cuisine']}  |  "
                f"**Time:** {row['time_minutes']} mins  |  "
                f"**Serves (original):** {row['servings']} → **cooking for:** {people}"
            )

            # Allergy substitution suggestions (for allergens that slipped
            # through, e.g. partial matches) — defensive, usually empty here.
            if allergies:
                flagged = [a for a in allergies if a in row["ingredients"]]
                if flagged:
                    st.error(f"Contains: {', '.join(flagged)}")
                    for a in flagged:
                        st.markdown(f"- **{a}** → {substitute_dict.get(a, 'no known substitute')}")

            st.markdown("**Scaled ingredients:**")
            for item in scale_ingredients(row["ingredient_list"], row["servings"], people):
                st.markdown(f"- {item}")

            st.markdown(f"**Instructions:** {row['instructions']}")
            st.markdown("---")
    else:
        st.warning("No recipes matched. Try fewer ingredients, more time, or fewer allergy filters.")
else:
    st.info("Enter at least one ingredient above to get recommendations.")
