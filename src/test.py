import sys
import os
from datetime import datetime, timedelta

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.receipts.service.image_gen import ReceiptGenerator
from core.receipts.service.receipt_service import ReceiptService
from utilities.dbconfig import SessionLocal, engine
from core.receipts.model.Receipt import Base
import base64
from PIL import Image
import io

def create_test_database():
    """Create test database tables"""
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created")

def test_receipt_generator():
    """Test the receipt generator with different transaction types"""
    print("\n🧪 Testing Receipt Generator...")
    
    generator = ReceiptGenerator()
    
    # Test data for different transaction types
    test_cases = [
        {
            "name": "Airtime Purchase",
            "data": {
                'transaction_type': 'Airtime Purchase',
                'amount': '25.00',
                'status': 'Completed',
                'transaction_id': 'TXN123456789',
                'sender': 'User123',
                'receiver': '0241234567',
                'payment_method': 'Mobile Money',
                'timestamp': datetime.now()
            }
        }
        # },
        # {
        #     "name": "Money Transfer",
        #     "data": {
        #         'transaction_type': 'Money Transfer',
        #         'amount': '150.50',
        #         'status': 'Completed',
        #         'transaction_id': 'TXN987654321',
        #         'sender': 'User456',
        #         'receiver': '0247654321',
        #         'payment_method': 'Mobile Money',
        #         'timestamp': datetime.now()
        #     }
        # },
        # {
        #     "name": "Bill Payment",
        #     "data": {
        #         'transaction_type': 'Bill Payment',
        #         'amount': '89.75',
        #         'status': 'Pending',
        #         'transaction_id': 'TXN555666777',
        #         'sender': 'User789',
        #         'receiver': 'ECG Ghana',
        #         'payment_method': 'Mobile Money',
        #         'timestamp': datetime.now()
        #     }
        # },
        # {
        #     "name": "Loan Disbursement",
        #     "data": {
        #         'transaction_type': 'Loan Disbursement',
        #         'amount': '1000.00',
        #         'status': 'Completed',
        #         'transaction_id': 'LOAN888999000',
        #         'sender': 'Lebe Financial',
        #         'receiver': '0241234567',
        #         'payment_method': 'Mobile Money',
        #         'timestamp': datetime.now(),
        #         'interest_rate': '5',
        #         'loan_period': '30 days',
        #         'expected_pay_date': (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
        #         'penalty_rate': '2'
        #     }
        # },
        # {
        #     "name": "Large Amount Loan",
        #     "data": {
        #         'transaction_type': 'Loan',
        #         'amount': '5000.00',
        #         'status': 'Completed',
        #         'transaction_id': 'LOAN111222333',
        #         'sender': 'Lebe Financial',
        #         'receiver': '0249876543',
        #         'payment_method': 'Bank Transfer',
        #         'timestamp': datetime.now(),
        #         'interest_rate': '7.5',
        #         'loan_period': '90 days',
        #         'expected_pay_date': (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d"),
        #         'penalty_rate': '3.5'
        #     }
        # }
    ]
    
    # Create test_output directory if it doesn't exist
    output_dir = "test_output"
    os.makedirs(output_dir, exist_ok=True)
    
    for test_case in test_cases:
        print(f"\n📄 Generating receipt for: {test_case['name']}")
        
        try:
            # Generate receipt image
            image_url = generator.generate_receipt_image(test_case['data'])
            
            # Print image url
            print(f"✅ Receipt image URL generated (truncated): {image_url[:50]}...")
            
            # Extract base64 data from URL
            base64_data = image_url.split(',')[1]
            image_data = base64.b64decode(base64_data)
            
            # Save image to file
            filename = f"{output_dir}/{test_case['name'].lower().replace(' ', '_')}.png"
            with open(filename, 'wb') as f:
                f.write(image_data)
            
            # Display image info
            image = Image.open(io.BytesIO(image_data))
            print(f"✅ Saved: {filename}")
            print(f"   Size: {image.size} pixels")
            print(f"   Format: {image.format}")
            print(f"   Mode: {image.mode}")
            
        except Exception as e:
            print(f"❌ Error generating {test_case['name']}: {e}")

def test_receipt_service():
    """Test the receipt service with database operations"""
    print("\n\n🧪 Testing Receipt Service with Database...")
    
    db = SessionLocal()
    try:
        service = ReceiptService(db)
        
        # Test creating a receipt
        print("📝 Creating receipt in database...")
        
        image_url = service.create_receipt(
            transaction_id="TEST_TXN_001",
            user_id="test_user_123",
            transaction_type="Money Transfer",
            amount="75.25",
            status="Completed",
            sender="test_sender",
            receiver="test_receiver",
            payment_method="Mobile Money",
            timestamp=datetime.now()
        )
        
        print(f"✅ Receipt created successfully!")
        print(f"📸 Image URL length: {len(image_url)} characters")
        print(f"🌐 URL prefix: {image_url[:50]}...")
        
        # Test retrieving receipt by transaction ID
        print("\n🔍 Retrieving receipt by transaction ID...")
        retrieved_url = service.get_receipt_image_url_by_transaction("TEST_TXN_001")
        print(f"✅ Retrieved URL length: {len(retrieved_url)} characters")
        
        # Test getting user receipts
        print("\n👤 Getting user's recent receipts...")
        user_receipts = service.get_user_receipts("test_user_123", limit=5)
        print(f"✅ Found {len(user_receipts)} receipts for user")
        
        for receipt in user_receipts:
            print(f"   - {receipt.id}: {receipt.transaction_id}")
        
        # Save one receipt image from service
        if image_url:
            base64_data = image_url.split(',')[1]
            image_data = base64.b64decode(base64_data)
            filename = "test_output/service_generated_receipt.png"
            with open(filename, 'wb') as f:
                f.write(image_data)
            print(f"💾 Service-generated receipt saved: {filename}")
        
    except Exception as e:
        print(f"❌ Error in receipt service test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

def test_edge_cases():
    """Test edge cases and error handling"""
    print("\n\n⚠️ Testing Edge Cases...")
    
    generator = ReceiptGenerator()
    
    edge_cases = [
        {
            "name": "Missing Fields",
            "data": {
                'transaction_type': 'Test Transaction',
                'amount': '10.00',
                'status': 'Completed',
                # Missing other required fields
            }
        },
        {
            "name": "Very Long Transaction ID",
            "data": {
                'transaction_type': 'Test',
                'amount': '10.00',
                'status': 'Completed',
                'transaction_id': 'VERY_LONG_TRANSACTION_ID_THAT_SHOULD_WRAP_OR_TRUNCATE',
                'sender': 'Test Sender',
                'receiver': 'Test Receiver',
                'payment_method': 'Mobile Money',
                'timestamp': datetime.now()
            }
        },
        {
            "name": "Zero Amount",
            "data": {
                'transaction_type': 'Zero Amount Test',
                'amount': '0.00',
                'status': 'Completed',
                'transaction_id': 'ZERO_AMOUNT_TXN',
                'sender': 'Test Sender',
                'receiver': 'Test Receiver',
                'payment_method': 'Mobile Money',
                'timestamp': datetime.now()
            }
        },
        {
            "name": "Failed Transaction",
            "data": {
                'transaction_type': 'Failed Payment',
                'amount': '50.00',
                'status': 'Failed',
                'transaction_id': 'FAILED_TXN_001',
                'sender': 'Test Sender',
                'receiver': 'Test Receiver',
                'payment_method': 'Mobile Money',
                'timestamp': datetime.now()
            }
        }
    ]
    
    for test_case in edge_cases:
        print(f"\n🔧 Testing: {test_case['name']}")
        
        try:
            image_url = generator.generate_receipt_image(test_case['data'])
            
            if image_url:
                # Save the image
                base64_data = image_url.split(',')[1]
                image_data = base64.b64decode(base64_data)
                filename = f"test_output/edge_case_{test_case['name'].lower().replace(' ', '_')}.png"
                with open(filename, 'wb') as f:
                    f.write(image_data)
                print(f"✅ Saved: {filename}")
            else:
                print("❌ No image URL returned")
                
        except Exception as e:
            print(f"❌ Error in edge case '{test_case['name']}': {e}")

def main():
    """Main function to run all tests"""
    print("🚀 Starting Receipt Generation Unit Tests")
    print("=" * 50)
    
    # Create test output directory
    os.makedirs("test_output", exist_ok=True)
    
    try:
        # Create database tables
        create_test_database()
        
        # Test receipt generator
        test_receipt_generator()
        
        # Test receipt service with database
        test_receipt_service()
        
        # Test edge cases
        test_edge_cases()
        
        print("\n" + "=" * 50)
        print("🎉 All tests completed!")
        print(f"📁 Check the 'test_output' directory for generated receipt images")
        print("💡 You can open the PNG files to view the receipts")
        
    except Exception as e:
        print(f"\n💥 Critical error during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()