from PIL import Image, ImageDraw, ImageFont
import io
import base64
from datetime import datetime
from typing import Dict, Any

class ReceiptGenerator:
    def __init__(self):
        pass

    def generate_receipt_image(self, receipt_data: Dict[str, Any]) -> str:
        """Generate receipt image and return base64 data URL"""
        is_loan = receipt_data.get('transaction_type', '').lower() in ['loan', 'loan disbursement', 'get_loan']

        if is_loan:
            image = self._generate_loan_receipt(receipt_data)
        else:
            image = self._generate_standard_receipt(receipt_data)

        buffered = io.BytesIO()
        image.save(buffered, format="PNG", optimize=True)
        img_str = base64.b64encode(buffered.getvalue()).decode()

        return f"data:image/png;base64,{img_str}"

    def _generate_standard_receipt(self, data: Dict[str, Any]) -> Image.Image:
        """Generate standard receipt with modern design"""
        width, height = 420, 720
        image = Image.new("RGBA", (width, height), (255, 255, 255, 255))
        draw = ImageDraw.Draw(image)

        # Colors
        primary_color = "#1a237e"
        accent_color = "#34A853"  # green success
        gray_text = "#666666"
        black_text = "#222222"
        light_gray_bg = "#F6F8FA"
        border_color = "#E0E0E0"

        # Fonts (try Poppins, fallback to Arial)
        try:
            title_font = ImageFont.truetype("Poppins-SemiBold.ttf", 24)
            subtitle_font = ImageFont.truetype("Poppins-Regular.ttf", 16)
            bold_font = ImageFont.truetype("Poppins-SemiBold.ttf", 14)
            regular_font = ImageFont.truetype("Poppins-Regular.ttf", 14)
            small_font = ImageFont.truetype("Poppins-Regular.ttf", 12)
        except:
            title_font = ImageFont.truetype("arialbd.ttf", 24)
            subtitle_font = ImageFont.truetype("arial.ttf", 16)
            bold_font = ImageFont.truetype("arialbd.ttf", 14)
            regular_font = ImageFont.truetype("arial.ttf", 14)
            small_font = ImageFont.truetype("arial.ttf", 12)

        # Draw rounded card background
        card_margin = 20
        card_radius = 30
        card_top = 40
        card_bottom = height - 40
        draw.rounded_rectangle(
            [card_margin, card_top, width - card_margin, card_bottom],
            radius=card_radius,
            fill="white",
            outline=border_color,
            width=1,
        )

        # Success circle icon
        center_x = width // 2
        icon_y = card_top + 50
        r = 30
        draw.ellipse([center_x - r, icon_y - r, center_x + r, icon_y + r], fill=accent_color)

        # Draw checkmark (vector)
        check_size = 16
        cx, cy = center_x, icon_y
        draw.line([(cx - check_size // 2, cy), (cx, cy + check_size // 2)], fill="white", width=4)
        draw.line([(cx, cy + check_size // 2), (cx + check_size, cy - check_size // 2)], fill="white", width=4)

        # Header Text
        y = icon_y + 60
        draw.text((center_x, y), data["transaction_type"], font=title_font, fill=black_text, anchor="mm")
        y += 35
        draw.text((center_x, y), "Successful!", font=title_font, fill=black_text, anchor="mm")

        # Subtext
        y += 30
        draw.text((center_x, y), "Your lebe process was successful.", font=subtitle_font, fill=gray_text, anchor="mm")

        # Info box
        box_top = y + 40
        box_left = card_margin + 20
        box_right = width - card_margin - 20
        box_bottom = card_bottom - 40
        draw.rounded_rectangle([box_left, box_top, box_right, box_bottom], radius=15, fill=light_gray_bg)

        # Draw transaction info
        info_x = box_left + 20
        y = box_top + 25

        # Amount
        draw.text((info_x, y), "Amount", font=regular_font, fill=gray_text)
        draw.text((box_right - 20, y), f"GHC {data.get('amount', '0.00')}", font=bold_font, fill=black_text, anchor="ra")
        y += 35

        # Status Tag
        draw.text((info_x, y), "Status", font=regular_font, fill=gray_text)
        tag_text = data.get("status", "Success")
        tag_width = 70
        tag_height = 24
        tag_x = box_right - 20 - tag_width
        tag_y = y - 4
        draw.rounded_rectangle([tag_x, tag_y, tag_x + tag_width, tag_y + tag_height], radius=12, fill="#E6F4EA")
        draw.text((tag_x + tag_width / 2, tag_y + tag_height / 2), tag_text, font=small_font, fill=accent_color, anchor="mm")
        y += 40

        # Line separator
        draw.line([(info_x, y), (box_right - 20, y)], fill=border_color, width=1)
        y += 20

        # Other fields
        fields = [
            ("Transaction Type", data.get("transaction_type", "N/A")),
            ("Transaction ID", data.get("transaction_id", "N/A")),
            ("Sender", data.get("sender", "N/A")),
            ("Receiver", data.get("receiver", "N/A")),
            ("Payment Method", data.get("payment_method", "N/A")),
            ("Timestamp", data.get("timestamp", datetime.now()).strftime("%b %d, %Y, %H:%M:%S")
             if hasattr(data.get("timestamp"), "strftime") else str(data.get("timestamp", "N/A"))),
        ]

        for label, value in fields:
            draw.text((info_x, y), label, font=regular_font, fill=gray_text)
            draw.text((box_right - 20, y), value, font=bold_font, fill=black_text, anchor="ra")
            y += 35

        return image

    def _generate_loan_receipt(self, data: Dict[str, Any]) -> Image.Image:
        """Generate loan receipt with loan-specific styled layout"""
        width, height = 420, 820  # taller for loan details
        image = Image.new("RGBA", (width, height), (255, 255, 255, 255))
        draw = ImageDraw.Draw(image)

        # Colors
        primary_color = "#1a237e"
        accent_color = "#34A853"  # green success
        gray_text = "#666666"
        black_text = "#222222"
        light_gray_bg = "#F6F8FA"
        border_color = "#E0E0E0"
        danger_color = "#d32f2f"

        # Fonts
        try:
            title_font = ImageFont.truetype("Poppins-SemiBold.ttf", 24)
            subtitle_font = ImageFont.truetype("Poppins-Regular.ttf", 16)
            bold_font = ImageFont.truetype("Poppins-SemiBold.ttf", 14)
            regular_font = ImageFont.truetype("Poppins-Regular.ttf", 14)
            small_font = ImageFont.truetype("Poppins-Regular.ttf", 12)
        except:
            title_font = ImageFont.truetype("arialbd.ttf", 24)
            subtitle_font = ImageFont.truetype("arial.ttf", 16)
            bold_font = ImageFont.truetype("arialbd.ttf", 14)
            regular_font = ImageFont.truetype("arial.ttf", 14)
            small_font = ImageFont.truetype("arial.ttf", 12)

        # Card
        card_margin = 20
        card_radius = 30
        card_top = 40
        card_bottom = height - 40
        draw.rounded_rectangle(
            [card_margin, card_top, width - card_margin, card_bottom],
            radius=card_radius,
            fill="white",
            outline=border_color,
            width=1,
        )

        # Success icon
        center_x = width // 2
        icon_y = card_top + 50
        r = 30
        draw.ellipse([center_x - r, icon_y - r, center_x + r, icon_y + r], fill=accent_color)
        check_size = 16
        cx, cy = center_x, icon_y
        draw.line([(cx - check_size // 2, cy), (cx, cy + check_size // 2)], fill="white", width=4)
        draw.line([(cx, cy + check_size // 2), (cx + check_size, cy - check_size // 2)], fill="white", width=4)

        # Title
        y = icon_y + 60
        draw.text((center_x, y), "Loan Disbursement", font=title_font, fill=black_text, anchor="mm")
        y += 35
        draw.text((center_x, y), "Successful!", font=title_font, fill=black_text, anchor="mm")

        # Subtext
        y += 28
        draw.text((center_x, y), "Your loan has been disbursed to the receiver.", font=subtitle_font, fill=gray_text, anchor="mm")

        # Info box (standard fields)
        box_top = y + 36
        box_left = card_margin + 20
        box_right = width - card_margin - 20
        box_bottom = card_bottom - 200
        draw.rounded_rectangle([box_left, box_top, box_right, box_bottom], radius=15, fill=light_gray_bg)

        info_x = box_left + 20
        y = box_top + 25

        # Standard fields inside info box
        standard_fields = [
            ("Transaction Type", data.get('transaction_type', 'Loan Disbursement')),
            ("Amount", f"GHS {data.get('amount', '0.00')}"),
            ("Status", data.get('status', 'Success')),
            ("Transaction ID", data.get('transaction_id', 'N/A')),
            ("Sender", data.get('sender', 'Lebe Financial')),
            ("Receiver", data.get('receiver', 'N/A')),
            ("Payment Method", data.get('payment_method', 'N/A')),
            ("Timestamp", data.get('timestamp', datetime.now()).strftime("%b %d, %Y, %H:%M:%S")
             if hasattr(data.get("timestamp"), "strftime") else str(data.get("timestamp", "N/A"))),
        ]

        for label, value in standard_fields:
            draw.text((info_x, y), label, font=regular_font, fill=gray_text)
            # amount colored green, status pill, others bold
            if label == "Amount":
                draw.text((box_right - 20, y), value, font=bold_font, fill=accent_color, anchor="ra")
            elif label == "Status":
                tag_text = value
                tag_w = 80
                tag_h = 26
                tx = box_right - 20 - tag_w
                ty = y - 6
                draw.rounded_rectangle([tx, ty, tx + tag_w, ty + tag_h], radius=13, fill="#E6F4EA")
                draw.text((tx + tag_w / 2, ty + tag_h / 2), tag_text, font=small_font, fill=accent_color, anchor="mm")
            else:
                draw.text((box_right - 20, y), value, font=bold_font, fill=black_text, anchor="ra")
            y += 36

        # Loan-specific section header
        sec_top = box_bottom + 20
        draw.line([(box_left, sec_top), (box_right, sec_top)], fill=border_color, width=1)
        sec_top += 12
        draw.text((width//2, sec_top), "LOAN DETAILS", font=subtitle_font, fill=primary_color, anchor="mm")

        # Loan-specific fields
        y = sec_top + 30
        loan_fields = [
            ("Interest Rate", f"{data.get('interest_rate', '0')}%"),
            ("Loan Period", data.get('loan_period', 'N/A')),
            ("Expected Pay Date", data.get('expected_pay_date', 'N/A')),
            ("Penalty Rate", f"{data.get('penalty_rate', '0')}%"),
        ]

        for label, value in loan_fields:
            draw.text((info_x, y), label, font=regular_font, fill=gray_text)
            # color rates with danger_color (red) for emphasis
            if label in ["Interest Rate", "Penalty Rate"]:
                draw.text((box_right - 20, y), value, font=bold_font, fill=danger_color, anchor="ra")
            else:
                draw.text((box_right - 20, y), value, font=bold_font, fill=black_text, anchor="ra")
            y += 34

        # Footer
        footer_y = card_bottom - 40
        draw.line([(box_left, footer_y - 18), (box_right, footer_y - 18)], fill=border_color, width=1)
        draw.text((width//2, footer_y), "Manage your loan in the Lebe app!", fill=gray_text, font=small_font, anchor="mm")

        return image
