from PIL import Image, ImageDraw, ImageFont
import io
import base64
from datetime import datetime
from typing import Dict, Any
import os

class ReceiptGenerator:
    def __init__(self):
        # Load check icons (you'll need to provide the actual file paths)
        """
        :param assets_dir: Directory containing icon images (e.g., success_icon.png, failed_icon.png)
        """
        self.assets_dir = assets_dir = os.path.dirname(__file__) + "/assets"
        self.success_icon = self._load_icon(os.path.join(assets_dir, "success_icon.png"))
        self.failed_icon = self._load_icon(os.path.join(assets_dir, "failed_icon.png"))
        
    def _load_icon(self, icon_path: str) -> Image.Image:
        """Load and resize check icon"""
        try:
            icon = Image.open(icon_path).convert("RGBA")
            # Resize to appropriate size for the circle
            icon = icon.resize((26, 26), Image.Resampling.LANCZOS)
            return icon
        except FileNotFoundError:
            print(f"Warning: Icon file {icon_path} not found. Using fallback drawing.")
            return None
        except Exception as e:
            print(f"Warning: Could not load icon {icon_path}: {e}. Using fallback drawing.")
            return None

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
        is_failed = data.get('status', '').lower() == 'failed'
        if is_failed:
            accent_color = "#FFEBEE"
            icon_color = "#d32f2f"  # Red for failed
        else:
            accent_color = "#E6F4EA"
            icon_color = "#34A853"  # Green for success
            
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
        card_radius = 15
        card_top = 40
        card_bottom = height - 40
        draw.rounded_rectangle(
            [card_margin, card_top, width - card_margin, card_bottom],
            radius=card_radius,
            fill="white",
            outline=border_color,
            width=1,
        )

        # Success/Failed circle icon
        center_x = width // 2
        icon_y = card_top + 50
        r = 30
        draw.ellipse([center_x - r, icon_y - r, center_x + r, icon_y + r], fill=accent_color)


        # icon_to_use = self.failed_icon if is_failed else self.success_icon
        # # Calculate position to center the icon
        # icon_x = center_x - icon_to_use.width // 2
        # icon_y_pos = icon_y - icon_to_use.height // 2
        # # Paste the icon onto the image
        # image.paste(icon_to_use, (icon_x, icon_y_pos), icon_to_use)
            
        #Use image icon instead of drawn lines
        if (is_failed and self.failed_icon) or (not is_failed and self.success_icon):
            icon_to_use = self.failed_icon if is_failed else self.success_icon
            # Calculate position to center the icon
            icon_x = center_x - icon_to_use.width // 2
            icon_y_pos = icon_y - icon_to_use.height // 2
            # Paste the icon onto the image
            image.paste(icon_to_use, (icon_x, icon_y_pos), icon_to_use)
        else:
            # Fallback to drawn icon if image not available yet
            if is_failed:
                # Draw 'X' for failed
                cross_size = 14
                draw.line([
                    (center_x - cross_size, icon_y - cross_size),
                    (center_x + cross_size, icon_y + cross_size)
                ], fill=icon_color, width=4)
                draw.line([
                    (center_x + cross_size, icon_y - cross_size),
                    (center_x - cross_size, icon_y + cross_size)
                ], fill=icon_color, width=4)
            else:
                # Draw checkmark for success
                check_size = 10
                draw.line([
                    (center_x - check_size // 2, icon_y),
                    (center_x, icon_y + check_size // 2)
                ], fill=icon_color, width=4)
                draw.line([
                    (center_x, icon_y + check_size // 2),
                    (center_x + check_size, icon_y - check_size // 2)
                ], fill=icon_color, width=4)

        # Header Text
        y = icon_y + 60
        draw.text((center_x, y), data["transaction_type"], font=title_font, fill=black_text, anchor="mm")
        y += 35
        status_text = "Failed!" if is_failed else "Successful!"
        draw.text((center_x, y), status_text, font=title_font, fill=black_text, anchor="mm")

        # Subtext
        y += 30
        if is_failed:
            subtext = "Your lebe process failed."
        else:
            subtext = "Your lebe process was successful."
        draw.text((center_x, y), subtext, font=subtitle_font, fill=gray_text, anchor="mm")

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
        
        # Use red for failed status, green for successful
        tag_bg_color = "#FFEBEE" if is_failed else "#E6F4EA"
        tag_text_color = "#d32f2f" if is_failed else "#34A853"
        
        draw.rounded_rectangle([tag_x, tag_y, tag_x + tag_width, tag_y + tag_height], radius=12, fill=tag_bg_color)
        draw.text((tag_x + tag_width / 2, tag_y + tag_height / 2), tag_text, font=small_font, fill=tag_text_color, anchor="mm")
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
        width, height = 420, 820
        image = Image.new("RGBA", (width, height), (255, 255, 255, 255))
        draw = ImageDraw.Draw(image)

        # Colors
        primary_color = "#1a237e"
        is_failed = data.get('status', '').lower() == 'failed'
        if is_failed:
            accent_color = "#FFEBEE"
            icon_color = "#d32f2f"
        else:
            accent_color = "#E6F4EA"
            icon_color = "#34A853"
            
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

        # Success/Failed icon
        center_x = width // 2
        icon_y = card_top + 50
        r = 30
        draw.ellipse([center_x - r, icon_y - r, center_x + r, icon_y + r], fill=accent_color)

        # Use image icon
        if (is_failed and self.failed_icon) or (not is_failed and self.success_icon):
            icon_to_use = self.failed_icon if is_failed else self.success_icon
            icon_x = center_x - icon_to_use.width // 2
            icon_y_pos = icon_y - icon_to_use.height // 2
            image.paste(icon_to_use, (icon_x, icon_y_pos), icon_to_use)
        else:
            # Fallback drawing
            if is_failed:
                cross_size = 16
                draw.line([
                    (center_x - cross_size, icon_y - cross_size),
                    (center_x + cross_size, icon_y + cross_size)
                ], fill="white", width=4)
                draw.line([
                    (center_x + cross_size, icon_y - cross_size),
                    (center_x - cross_size, icon_y + cross_size)
                ], fill="white", width=4)
            else:
                check_size = 16
                draw.line([
                    (center_x - check_size // 2, icon_y),
                    (center_x, icon_y + check_size // 2)
                ], fill="white", width=4)
                draw.line([
                    (center_x, icon_y + check_size // 2),
                    (center_x + check_size, icon_y - check_size // 2)
                ], fill="white", width=4)

        # Title
        y = icon_y + 60
        status_text = "Failed!" if is_failed else "Successful!"
        draw.text((center_x, y), "Loan Disbursement", font=title_font, fill=black_text, anchor="mm")
        y += 35
        draw.text((center_x, y), status_text, font=title_font, fill=black_text, anchor="mm")

        # Subtext
        y += 28
        if is_failed:
            subtext = "Your loan disbursement failed."
        else:
            subtext = "Your loan has been disbursed to the receiver."
        draw.text((center_x, y), subtext, font=subtitle_font, fill=gray_text, anchor="mm")

        # Rest of the loan receipt code remains the same...
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
            if label == "Amount":
                draw.text((box_right - 20, y), value, font=bold_font, fill=icon_color, anchor="ra")
            elif label == "Status":
                tag_text = value
                tag_w = 80
                tag_h = 26
                tx = box_right - 20 - tag_w
                ty = y - 6
                tag_bg = "#FFEBEE" if is_failed else "#E6F4EA"
                tag_fg = "#d32f2f" if is_failed else "#34A853"
                draw.rounded_rectangle([tx, ty, tx + tag_w, ty + tag_h], radius=13, fill=tag_bg)
                draw.text((tx + tag_w / 2, ty + tag_h / 2), tag_text, font=small_font, fill=tag_fg, anchor="mm")
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