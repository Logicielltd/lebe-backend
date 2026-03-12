# Payflow NLU Detection Improvements

## Problem Statement
When users tried to use payflows (e.g., "Use Get Manager Airtime"), the AI was confusing them with regular transactions and attempting to extract missing slots for a `buy_airtime` intent instead of recognizing them as `execute_payflow` intents.

### Example Error
```
User: "Use Get Manager Airtime"
❌ BEFORE: Detected as buy_airtime with missing slots [phone_number, amount, beneficiary_name]
✅ AFTER: Detected as execute_payflow with payflow_name="Get Manager Airtime"
```

## Root Causes Identified
1. **Missing Examples**: No examples in the intent detection prompt showing payflow execution vs regular transactions
2. **Insufficient Payflow System Prompt**: Payflows system prompt lacked detailed explanation of what they are and how to recognize them
3. **Weak Differentiation Rules**: No explicit rules for determining when a name refers to a payflow vs a beneficiary
4. **No Action Verb Patterns**: The prompt didn't recognize action verbs like "Use", "Send using", "Pay with" as payflow execution indicators

## Improvements Made

### 1. Enhanced Payflow System Prompt (`src/core/nlu/config.py`)

**Added:**
- Clear distinction between payflows (saved templates) and beneficiaries (contacts)
- **Key Recognition Patterns**:
  - `"Use [Name]"` → Execute payflow
  - `"Send using [Name]"` → Execute payflow
  - `"Pay with [Name]"` → Execute payflow
  - `"[Name] of [Amount]"` → Execute payflow with amount override (when Name is descriptive)
  - `"View/Show templates"` → View payflows
  - `"Delete [Name]"` → Delete payflow
  - `"Rename/Update [Name]"` → Update payflow

- **Examples of Payflow Names**:
  - "Mom Payment" - specific, descriptive
  - "Get Manager Airtime" - specific, descriptive
  - "Electricity Bill" - specific, descriptive
  - "John Airtime" - specific, descriptive
  - "Rent Payment" - specific, descriptive

- **Comparison Examples**:
  - "Send to John" → `send_money` with beneficiary_name (generic)
  - "Use John Airtime" → `execute_payflow` with payflow_name (descriptive/template)
  - "Buy airtime for John" → `buy_airtime` with beneficiary_name (generic)
  - "John Airtime of 50" → `execute_payflow` with amount override (descriptive/template)

### 2. Enhanced Intent Detection Prompt (`intents.py`)

**Added to `intent_guidelines`:**
```
3. **CRITICAL PAYFLOW vs BENEFICIARY DETECTION** (High Priority):
- Keywords "Use", "Send using", "Pay with" + NAME → ALWAYS execute_payflow
- Compound/Descriptive names + amount = likely payflow
- Generic single names without payflow action verbs = likely beneficiary_name
- If name matches known payflow patterns, prefer execute_payflow
- Payflow names typically describe the transaction type + recipient/purpose

4. **Payflow Action Pattern Recognition**:
- "Use [Name]" → execute_payflow (highest confidence)
- "Send using [Name]" → execute_payflow (highest confidence)
- "Pay with [Name]" → execute_payflow (highest confidence)
- [Payflow Name] of [Amount]" → execute_payflow with amount override
```

**Added Comprehensive Examples:**
10+ detailed examples showing payflow execution vs beneficiary detection:
- `"Use Get Manager Airtime"` → `execute_payflow` with `payflow_name="Get Manager Airtime"`
- `"Send using Mom Payment"` → `execute_payflow` with `payflow_name="Mom Payment"`
- `"Pay with Electricity Bill"` → `execute_payflow` with `payflow_name="Electricity Bill"`
- `"Mom Payment of 50"` → `execute_payflow` with amount override
- `"Buy airtime for John"` → `buy_airtime` with `beneficiary_name="John"` (comparison)
- `"Use John Airtime"` → `execute_payflow` with `payflow_name="John Airtime"` (same person, different intent!)

### 3. Improved Confidence Scoring

**Updated confidence categories:**
```
HIGH: 
- User message contains "Use [Name]", "Send using [Name]", "Pay with [Name]" → execute_payflow
- Payflow-specific action verbs detected with identifiable payflow name

MEDIUM:
- Compound names without explicit action verbs (could be payflow or beneficiary)
- User message has partial payflow indicators

LOW:
- Single generic name alone (John, Mom) without payflow action verbs
- Insufficient information to determine payflow vs beneficiary
```

### 4. Added Payflow-Final Checks

```
PAYFLOW-SPECIFIC FINAL CHECKS:
- If message contains "Use", "Send using", "Pay with" + name → MUST be execute_payflow
- If message is "[Descriptive Name] of [Amount]" → Treat as execute_payflow
- Single generic names (John, Mary) alone = beneficiary lookup, NOT payflow
- Compound/descriptive names = payflow names
```

### 5. Clarified Beneficiary vs Payflow Rules

**Key Rule Override:**
```
IMPORTANT RULE FOR PAYFLOW DETECTION (OVERRIDES BENEFICIARY WHEN ACTION VERB PRESENT):
- When user says "Use [Name]", "Send using [Name]", or "Pay with [Name]" 
  → This is ALWAYS execute_payflow, NOT a beneficiary lookup
- The name is payflow_name, not beneficiary_name
- Payflows are saved TEMPLATES with specific names created by the user
```

## Expected Behavior After Changes

### Test Case 1: Basic Payflow Execution
```
Input: "Use Get Manager Airtime"
Expected Output:
  INTENT: execute_payflow
  SLOTS: {"payflow_name": "Get Manager Airtime"}
  MISSING: 
  CONFIDENCE: HIGH
```

### Test Case 2: Payflow with Amount Override
```
Input: "Mom Payment of 50"
Expected Output:
  INTENT: execute_payflow
  SLOTS: {"payflow_name": "Mom Payment", "amount": "50"}
  MISSING: 
  CONFIDENCE: HIGH
```

### Test Case 3: Payflow vs Beneficiary (Same Name)
```
Input: "Buy airtime for John"
Expected Output:
  INTENT: buy_airtime
  SLOTS: {"beneficiary_name": "John"}
  MISSING: amount
  CONFIDENCE: MEDIUM

Input: "Use John Airtime"
Expected Output:
  INTENT: execute_payflow
  SLOTS: {"payflow_name": "John Airtime"}
  MISSING: 
  CONFIDENCE: HIGH
```

### Test Case 4: View Payflows
```
Input: "Show my payment templates"
Expected Output:
  INTENT: view_payflows
  SLOTS: {}
  MISSING: 
  CONFIDENCE: HIGH
```

### Test Case 5: Delete Payflow
```
Input: "Delete Electricity Bill"
Expected Output:
  INTENT: delete_payflow
  SLOTS: {"payflow_name": "Electricity Bill"}
  MISSING: 
  CONFIDENCE: HIGH
```

## Key Takeaways

1. **Action Verbs are Key**: "Use", "Send using", "Pay with" strongly indicate payflow execution
2. **Descriptive Names**: Compound/descriptive names (2+ words, include transaction type) = likely payflows
3. **Generic Names Need Context**: Single names like "John" or "Mom" alone = beneficiary, not payflow
4. **Order of Detection**: Check for action verb + name pattern FIRST before defaulting to other intents
5. **Confidence Matters**: HIGH confidence for payflow when action verbs present; MEDIUM-LOW when ambiguous

## Files Modified

1. **`src/core/nlu/config.py`**
   - Enhanced `"payflows"` system prompt with detailed payflow vs beneficiary distinction
   - Added recognition patterns and examples
   - Added specific rules for payflow execution

2. **`intents.py`**
   - Enhanced `intent_guidelines` with payflow-specific detection rules
   - Added 10+ detailed payflow examples to the examples section
   - Updated confidence scoring with payflow-priority rules
   - Added payflow-specific final accuracy checks
   - Clarified beneficiary vs payflow rules with action verb triggers

## How to Test

1. **Test Payflow Recognition**:
   ```
   Send message: "Use Get Manager Airtime"
   Verify: Intent detected as execute_payflow, NOT buy_airtime
   ```

2. **Test Payflow vs Beneficiary (Same Name)**:
   ```
   Send message: "Buy airtime for John"
   Verify: Intent detected as buy_airtime with beneficiary_name="John"
   
   Send message: "Use John Airtime"
   Verify: Intent detected as execute_payflow with payflow_name="John Airtime"
   ```

3. **Test Payflow with Amount Override**:
   ```
   Send message: "Mom Payment of 50"
   Verify: Intent detected as execute_payflow with payflow_name and amount
   ```

4. **Test View Payflows**:
   ```
   Send message: "Show my templates"
   Verify: Intent detected as view_payflows
   ```

## Next Steps (Optional Enhancements)

1. **Add Payflow Lookup Service**: Backend should maintain a list of user's saved payflows and log accuracy when matching names
2. **Fallback Handling**: If payflow name not found, suggest "Did you mean..." options
3. **Training Data**: Collect real user payflow requests to further refine the prompt
4. **A/B Testing**: Compare accuracy before and after changes using real user messages
5. **Confidence Threshold**: Only execute payflows if confidence is HIGH
