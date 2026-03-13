# Payflow Documentation

## Overview

**Payflow** is a powerful feature that allows users to save payment templates (snapshots) of successful payment transactions for quick reuse. A payflow captures all the details of a successful payment session and can be repeated with minimal interaction.

## What is a Payflow?

A payflow is a **saved snapshot of a successful payment session** that contains:
- **Intent Name**: The type of transaction (send_money, buy_airtime, pay_bill, etc.)
- **Slot Values**: All required information filled in during the transaction (recipient, amount, provider, etc.)
- **Payment Method**: The network/provider used
- **Transaction Details**: Recipient phone, account numbers, bill provider, etc.
- **Metadata**: Creation date, last usage, usage count, etc.

### Example Payflows
1. **"Mom Payment"** - A send_money payflow to send to a specific family member
2. **"Electricity Bill"** - A pay_bill payflow for monthly utility payments  
3. **"John Airtime"** - A buy_airtime payflow for a friend's phone top-up
4. **"Rent Payment"** - A monthly bill payment payflow

## How Payflows Work

### 1. Creating a Payflow

A payflow can **ONLY be saved after a successful transaction** where all required intent slots are populated.

**Workflow:**
```
User initiates payment
    ↓
User provides all required information
    ↓
System confirms payment details
    ↓
User authorizes with PIN
    ↓
❌ Payment successful!
    ↓
System offers: "Would you like to save this as a payment template?"
    ↓
User says: "Save as [Payflow Name]"
    ↓
✅ Payflow created and saved
```

### 2. Executing a Payflow

Users can quickly repeat a payflow without re-entering all information.

**Workflow:**
```
User says: "Use [Payflow Name]" or "Send using [Payflow Name]"
    ↓
System identifies and retrieves the payflow
    ↓
System optionally asks to override amount if needed
    ↓
If confirmation required:
    System shows confirmation with saved details
    User confirms with PIN
    ↓
If direct payment:
    Payment initiated automatically
    ↓
✅ Transaction processed with saved details
```

## Payflow Management

### Supported Operations

#### 1. **View Payflows**
- List all saved payflows
- Filter by transaction type (send_money, buy_airtime, etc.)
- See usage statistics

**Command:** `View my payment templates`

**Response:**
```
Your saved payment templates:
✅ Mom Payment: Send money - Requires confirmation - Used 5 times
✅ Electricity Bill: Pay bill - Requires confirmation - Used 3 times
✅ John Airtime: Buy airtime - Quick pay - Used 8 times
```

#### 2. **Execute Payflow**
- Repeat a saved payflow
- Optionally override the amount
- Quick payment with saved details

**Commands:**
- `Use Mom Payment`
- `Send using Mom Payment`
- `Pay using Electricity Bill`
- `Send Mom Payment of GHS 50` (overrides saved amount)

#### 3. **Update Payflow**
- Change the payflow name
- Update the default amount
- Modify confirmation requirements

**Commands:**
- `Rename Mom Payment to Mother Payment`
- `Update Electricity Bill to GHS 75`

#### 4. **Delete Payflow**
- Remove a saved payflow
- Payflow becomes inactive but records remain for history

**Command:** `Remove Mom Payment`

## Intent Detection with Payflows

The NLU system has been enhanced to recognize payflow names in user messages. When a user mentions a payflow name, the system will:

1. **Identify the payflow name** from the user's message
2. **Verify it exists** in the user's saved payflows
3. **Extract all saved slot values** for the payflow
4. **Prepare for payment execution** with those slots
5. **Ask for confirmation** (if required by the payflow)
6. **Initiate payment** with the saved details

### Example Interactions

**User:** "Send using Mom Payment"
```
System: "Ready to replay your 'Mom Payment' template (Send Money, Amount: GHS 100). 
         Your transfer will go to 0541234567 (Ama). Please confirm with your PIN."
```

**User:** "John Airtime of 50"
```
System: "I found your 'John Airtime' template. Would you like to update the amount from GHS 10 to GHS 50?
         Recipient: John (0551111111) on MTN. Confirm with PIN."
```

## API Endpoints

### Payflow Management

#### Save a Payflow
```
POST /api/v1/payflows/save
Content-Type: application/json

{
  "name": "Mom Payment",
  "description": "Weekly payment to mom",
  "intent_name": "send_money",
  "slot_values": {
    "recipient": "0541234567",
    "amount": "100",
    "reference": "weekly allowance"
  },
  "payment_method": "MTN",
  "recipient_phone": "0541234567",
  "recipient_name": "Ama Boateng",
  "requires_confirmation": true
}
```

#### List Payflows
```
GET /api/v1/payflows/list?intent=send_money

Response:
{
  "total": 2,
  "payflows": [
    {
      "id": 1,
      "name": "Mom Payment",
      "intent_name": "send_money",
      "slot_values": {...},
      "payment_method": "MTN",
      "recipient_phone": "0541234567",
      "recipient_name": "Ama Boateng",
      "requires_confirmation": true,
      "last_used_at": "2025-03-10T14:30:00",
      "created_at": "2025-02-15T10:20:00"
    },
    ...
  ]
}
```

#### Get Payflow Details
```
GET /api/v1/payflows/{payflow_id}
```

#### Update Payflow
```
PUT /api/v1/payflows/{payflow_id}
Content-Type: application/json

{
  "name": "Weekly Mom Payment",
  "last_amount": "150",
  "requires_confirmation": false
}
```

#### Execute Payflow
```
POST /api/v1/payflows/{payflow_id}/execute
Content-Type: application/json

{
  "amount": "120"  // Optional: override saved amount
}

Response:
{
  "success": true,
  "message": "Payflow prepared for execution",
  "slots": {
    "recipient": "0541234567",
    "amount": "120",
    "reference": "weekly allowance"
  }
}
```

#### Delete Payflow
```
DELETE /api/v1/payflows/{payflow_id}
```

## Database Structure

### Payflow Model
```python
class Payflow(Base):
    __tablename__ = "payflows"
    
    id: int (Primary Key)
    user_id: str (Foreign Key → users.id)
    name: str (User-friendly name)
    description: Optional[str]
    intent_name: str (The intent type: send_money, pay_bill, etc.)
    slot_values: JSON (Raw slot values)
    payment_method: str (MTN, VOD, AIR, BNK, etc.)
    recipient_phone: Optional[str]
    recipient_name: Optional[str]
    account_number: Optional[str] (For bill payments)
    bill_provider: Optional[str]
    last_amount: Optional[str]
    requires_confirmation: bool
    is_active: bool
    last_used_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
```

## Conversation Flow Integration

### Successful Payment → Payflow Offer
After any successful payment, the system automatically offers:

```
✅ [Success Message]

💾 Would you like to save this as a payment template for quick reuse? 
   Just say 'Save as [template name]' (e.g., 'Save as Mom Payment')
```

### User Saves Payflow
```
User: "Save as Mom Payment"

System: "Your payment template 'Mom Payment' has been saved successfully! ✅ 
         You can repeat this payment anytime by saying 'Send using Mom Payment'."
```

### Executing Saved Payflow
```
User: "Use Mom Payment"

System: "Ready to replay your 'Mom Payment' template (Send Money).
         Sending: GHS 100 to 0541234567 (Ama Boateng)
         Please confirm with your PIN to proceed."
```

### Quick Execution
For payflows marked as "direct payment" (no confirmation):
```
User: "Quick Mom"

System: "Initiating direct payment using 'Mom Payment' template...
         [Payment processes automatically]
         Transaction complete!"
```

## NLU Intent Configuration

Payflows are recognized through specific intents:

```python
"save_payflow": {
    "description": "Save a payment snapshot/template for quick reuse",
    "slots": ["payflow_name", "intent_name", "slot_values"],
    "required_slots": ["payflow_name"]
},
"view_payflows": {
    "description": "View saved payflows",
    "slots": ["intent_filter"],
    "required_slots": []
},
"execute_payflow": {
    "description": "Execute a saved payflow",
    "slots": ["payflow_name", "amount"],
    "required_slots": ["payflow_name"]
},
"delete_payflow": {
    "description": "Remove a saved payflow",
    "slots": ["payflow_name"],
    "required_slots": ["payflow_name"]
},
"update_payflow": {
    "description": "Edit a saved payflow",
    "slots": ["payflow_name", "update_field", "new_payflow_name"],
    "required_slots": ["payflow_name", "update_field"]
}
```

## Safety & Security Features

1. **Confirmation Requirements**: Users can choose to require PIN confirmation for each payflow execution
2. **One-Time Verification**: Payflow details are verified at creation time
3. **Audit Trail**: All payflow executions are logged as transactions
4. **Soft Deletion**: Deleted payflows are marked inactive, not removed
5. **User Isolation**: Payflows are strictly user-specific

## User Commands Summary

| Action | Commands |
|--------|----------|
| **View** | "Show my templates", "My payment templates", "View payflows" |
| **Save** | "Save as [name]", "Save this as [name]" (after successful payment) |
| **Execute** | "Use [name]", "Send using [name]", "Pay with [name]" |
| **Update** | "Rename [old name] to [new name]", "Update [name] to GHS 50" |
| **Delete** | "Remove [name]", "Delete [name]", "Forget [name]" |

## Best Practices

1. **Clear Names**: Use descriptive names like "Mom Payment" rather than "Payment1"
2. **Regular Updates**: Update payflows if recipient details change
3. **Amount Flexibility**: Consider allowing amount overrides for variable expenses
4. **Confirmation Levels**: Use quick pay for frequent, small transactions; require confirmation for larger amounts
5. **Organization**: Group similar payflows (e.g., "Bill: Electricity", "Transfer: Mom")

## Limitations & Constraints

1. **Requires Successful Base Transaction**: Can only be created after a complete, successful payment
2. **Slot Completeness**: All required slots must be populated
3. **Network Detection**: System auto-detects networks for new payflows
4. **Amount Flexibility**: Each payflow can be executed with different amounts via override
5. **Confirmation Settings**: Cannot be changed after creation (user must delete and recreate)

## Future Enhancements

1. **Payflow Groups**: Group related payflows
2. **Recurring Payflows**: Automatic execution on schedule
3. **Conditional Payflows**: Different behavior based on user balance
4. **Payflow Sharing**: Share templates with other users
5. **Analytics**: Insights on most-used payflows
6. **Templates Library**: Pre-made payflows for common transactions
