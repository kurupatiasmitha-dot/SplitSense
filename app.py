from flask import Flask, render_template, request, redirect, url_for, session
import os
import re
import pytesseract
from PIL import Image, ImageOps, ImageEnhance, ImageFilter


app = Flask(__name__)


# =========================================================
# SECRET KEY
# =========================================================

# Local computer:
# Uses "splitsense_secret_key" by default.
#
# Render:
# We can set SECRET_KEY as an environment variable.

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "splitsense_secret_key"
)


# =========================================================
# UPLOAD FOLDER
# =========================================================

UPLOAD_FOLDER = "uploads"

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# =========================================================
# TESSERACT PATH
# =========================================================

# First check if TESSERACT_PATH is provided
# by the deployment environment.

TESSERACT_PATH = os.environ.get(
    "TESSERACT_PATH"
)


if TESSERACT_PATH:

    # Used when an environment variable is provided.
    pytesseract.pytesseract.tesseract_cmd = (
        TESSERACT_PATH
    )

else:

    # -----------------------------------------------------
    # WINDOWS - LOCAL COMPUTER
    # -----------------------------------------------------

    if os.name == "nt":

        pytesseract.pytesseract.tesseract_cmd = (
            r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        )

    # -----------------------------------------------------
    # LINUX - RENDER / CLOUD
    # -----------------------------------------------------

    else:

        pytesseract.pytesseract.tesseract_cmd = (
            "tesseract"
        )


# =========================================================
# HOME
# =========================================================

@app.route("/")
def index():

    people = session.get(
        "people",
        []
    )

    return render_template(
        "index.html",

        people=people,

        items=session.get(
            "items",
            []
        ),

        subtotal=session.get(
            "subtotal",
            0
        ),

        cgst=session.get(
            "cgst",
            0
        ),

        sgst=session.get(
            "sgst",
            0
        ),

        total_gst=session.get(
            "total_gst",
            0
        ),

        grand_total=session.get(
            "grand_total",
            0
        ),

        shares=session.get(
            "shares",
            {}
        ),

        person_subtotals=session.get(
            "person_subtotals",
            {}
        ),

        person_gst=session.get(
            "person_gst",
            {}
        ),

        person_totals=session.get(
            "person_totals",
            {}
        ),

        detailed_shares=session.get(
            "detailed_shares",
            {}
        ),

        entered_quantities=session.get(
            "entered_quantities",
            {}
        ),

        error=session.get(
            "error",
            ""
        )
    )


# =========================================================
# ADD PERSON
# =========================================================

@app.route(
    "/add_person",
    methods=["POST"]
)
def add_person():

    name = request.form.get(
        "name",
        ""
    ).strip()


    if name:

        people = session.get(
            "people",
            []
        )


        # Avoid duplicate names
        if name not in people:

            people.append(name)


        session["people"] = people


        # Clear old split result
        session["shares"] = {}

        session["person_subtotals"] = {}

        session["person_gst"] = {}

        session["person_totals"] = {}

        session["detailed_shares"] = {}


    return redirect(
        url_for("index")
    )


# =========================================================
# REMOVE PERSON
# =========================================================

@app.route(
    "/remove_person/<path:name>"
)
def remove_person(name):

    people = session.get(
        "people",
        []
    )


    if name in people:

        people.remove(name)


    session["people"] = people


    # Clear old result because people changed
    session["shares"] = {}

    session["person_subtotals"] = {}

    session["person_gst"] = {}

    session["person_totals"] = {}

    session["detailed_shares"] = {}


    return redirect(
        url_for("index")
    )


# =========================================================
# NORMALIZE OCR QUANTITY
# =========================================================

def normalize_quantity(value):

    value = value.strip().lower()


    replacements = {

        "i": "1",

        "l": "1",

        "il": "1",

        "li": "1",

        "lh": "1",

        "ih": "1",

        "1l": "1",

        "l1": "1",

        "ii": "1",

        "ll": "1"
    }


    if value in replacements:

        value = replacements[value]


    try:

        number = float(value)


        if number.is_integer():

            return int(number)


        return number


    except:

        return None


# =========================================================
# IMAGE PREPROCESSING
# =========================================================

def preprocess_image(image):

    # Fix orientation
    image = ImageOps.exif_transpose(
        image
    )


    # Grayscale
    image = image.convert(
        "L"
    )


    # Improve contrast
    image = ImageEnhance.Contrast(
        image
    ).enhance(2)


    # Sharpen
    image = image.filter(
        ImageFilter.SHARPEN
    )


    return image


# =========================================================
# PARSE RECEIPT
# =========================================================

def parse_receipt(text):

    lines = [

        line.strip()

        for line in text.splitlines()

        if line.strip()
    ]


    items = []


    subtotal = 0

    cgst = 0

    sgst = 0

    grand_total = 0


    # =====================================================
    # ITEM EXTRACTION
    # =====================================================

    for i, line in enumerate(lines):

        clean_line = line.strip()


        # Remove serial number
        clean_line = re.sub(

            r"^\d+\s+",

            "",

            clean_line
        )


        lower_line = clean_line.lower()


        # -------------------------------------------------
        # IGNORE NON-ITEM LINES
        # -------------------------------------------------

        ignored_words = [

            "phone",

            "gstin",

            "invoice",

            "date",

            "table",

            "time",

            "cashier",

            "bill no",

            "token no",

            "tax invoice",

            "subtotal",

            "sub total",

            "cgst",

            "sgst",

            "grand total",

            "round off",

            "thank you",

            "fssai",

            "add on"
        ]


        if any(

            word in lower_line

            for word in ignored_words

        ):

            continue


        # -------------------------------------------------
        # ITEM FORMAT
        #
        # Mushroom Soup 2 70.00 140.00
        #
        # -------------------------------------------------

        match = re.match(

            r"^(.+?)\s+"

            r"([0-9]+(?:\.[0-9]+)?|"
            r"i|l|il|li|lh|ih|1l|l1|ii|ll)"

            r"\s+"

            r"([\d,]+\.\d{2})"

            r"\s+"

            r"([\d,]+\.\d{2})$",

            clean_line,

            re.IGNORECASE
        )


        if not match:

            continue


        name = match.group(
            1
        ).strip()


        quantity_text = match.group(
            2
        )


        price_text = match.group(
            3
        )


        amount_text = match.group(
            4
        )


        quantity = normalize_quantity(
            quantity_text
        )


        if quantity is None:

            continue


        price = float(

            price_text.replace(
                ",",
                ""
            )
        )


        amount = float(

            amount_text.replace(
                ",",
                ""
            )
        )


        # -------------------------------------------------
        # EXTRA NAME VALIDATION
        # -------------------------------------------------

        if any(

            word in name.lower()

            for word in [

                "phone",

                "gstin",

                "invoice",

                "date",

                "table",

                "cashier",

                "bill",

                "token",

                "subtotal",

                "cgst",

                "sgst",

                "grand",

                "total",

                "round",

                "fssai"
            ]

        ):

            continue


        # -------------------------------------------------
        # CHECK AMOUNT
        # -------------------------------------------------

        expected_amount = round(

            quantity * price,

            2
        )


        # OCR can have tiny errors.
        # Allow maximum difference of ₹1.

        if abs(

            expected_amount - amount

        ) > 1.0:

            continue


        # -------------------------------------------------
        # SPLIT ITEM NAME
        #
        # Example:
        #
        # Butter 1 239.00 239.00
        # Chicken
        #
        # becomes:
        #
        # Butter Chicken
        # -------------------------------------------------

        if i + 1 < len(lines):

            next_line = lines[
                i + 1
            ].strip()


            if (

                next_line

                and not re.match(
                    r"^\d+\s+",
                    next_line
                )

                and not re.search(
                    r"\d+\.\d+",
                    next_line
                )

                and not re.search(

                    r"subtotal|cgst|sgst|grand total|round off",

                    next_line,

                    re.IGNORECASE
                )

                and not any(

                    word in next_line.lower()

                    for word in [

                        "phone",

                        "gstin",

                        "invoice",

                        "date",

                        "table",

                        "cashier",

                        "bill",

                        "token"
                    ]
                )

                and len(next_line) < 30

            ):

                name = (

                    name

                    + " "

                    + next_line
                )


        items.append({

            "name": name,

            "quantity": quantity,

            "price": price,

            "amount": amount
        })


    # =====================================================
    # REMOVE DUPLICATES
    # =====================================================

    unique_items = []

    seen = set()


    for item in items:

        key = (

            item["name"].lower(),

            item["quantity"],

            item["price"],

            item["amount"]
        )


        if key not in seen:

            seen.add(key)

            unique_items.append(
                item
            )


    items = unique_items


    # =====================================================
    # SUBTOTAL
    # =====================================================

    for line in lines:

        lower = line.lower()


        if (

            "subtotal" in lower

            or "sub total" in lower

        ):

            numbers = re.findall(

                r"\d+(?:,\d{3})*(?:\.\d+)?",

                line
            )


            if numbers:

                subtotal = float(

                    numbers[-1].replace(
                        ",",
                        ""
                    )
                )


    # =====================================================
    # GST
    # =====================================================

    for line in lines:

        lower = line.lower()


        numbers = re.findall(

            r"\d+(?:,\d{3})*(?:\.\d+)?",

            line
        )


        if not numbers:

            continue


        values = [

            float(

                n.replace(
                    ",",
                    ""
                )
            )

            for n in numbers
        ]


        # -------------------------------------------------
        # CGST
        # -------------------------------------------------

        if "cgst" in lower:

            # Ignore GST rate 2.5
            # and take actual tax amount.

            possible = [

                x

                for x in values

                if x > 5
            ]


            if possible:

                cgst = possible[-1]


        # -------------------------------------------------
        # SGST
        # -------------------------------------------------

        elif "sgst" in lower:

            possible = [

                x

                for x in values

                if x > 5
            ]


            if possible:

                sgst = possible[-1]


    # =====================================================
    # GRAND TOTAL
    # =====================================================

    for line in lines:

        lower = line.lower()


        if "grand total" in lower:

            numbers = re.findall(

                r"\d+(?:,\d{3})*(?:\.\d+)?",

                line
            )


            if numbers:

                grand_total = float(

                    numbers[-1].replace(
                        ",",
                        ""
                    )
                )


    # =====================================================
    # FALLBACK SUBTOTAL
    # =====================================================

    calculated_subtotal = round(

        sum(

            item["amount"]

            for item in items

        ),

        2
    )


    if subtotal == 0:

        subtotal = calculated_subtotal


    # =====================================================
    # GST CORRECTION
    # =====================================================

    expected_gst = round(

        subtotal * 0.025,

        2
    )


    # If OCR GST is missing or suspicious,
    # calculate from 2.5%.

    if (

        cgst <= 5

        or abs(
            cgst - expected_gst
        ) > 1

    ):

        cgst = expected_gst


    if (

        sgst <= 5

        or abs(
            sgst - expected_gst
        ) > 1

    ):

        sgst = expected_gst


    total_gst = round(

        cgst + sgst,

        2
    )


    # =====================================================
    # GRAND TOTAL
    # =====================================================

    if grand_total == 0:

        grand_total = round(

            subtotal + total_gst,

            2
        )


    return (

        items,

        round(
            subtotal,
            2
        ),

        round(
            cgst,
            2
        ),

        round(
            sgst,
            2
        ),

        round(
            total_gst,
            2
        ),

        round(
            grand_total,
            2
        )
    )


# =========================================================
# UPLOAD RECEIPT
# =========================================================

@app.route(
    "/upload",
    methods=["POST"]
)
def upload():

    file = request.files.get(
        "receipt"
    )


    if not file or file.filename == "":

        session["error"] = (

            "Please select a receipt image."
        )


        return redirect(
            url_for("index")
        )


    filepath = os.path.join(

        app.config[
            "UPLOAD_FOLDER"
        ],

        file.filename
    )


    file.save(
        filepath
    )


    try:

        # -------------------------------------------------
        # OPEN IMAGE
        # -------------------------------------------------

        image = Image.open(
            filepath
        )


        # -------------------------------------------------
        # PREPROCESS
        # -------------------------------------------------

        processed_image = (

            preprocess_image(
                image
            )
        )


        # -------------------------------------------------
        # OCR
        #
        # OCR text is used internally only.
        # It is NOT displayed on webpage.
        # -------------------------------------------------

        text = pytesseract.image_to_string(

            processed_image,

            config="--psm 6"
        )


        # -------------------------------------------------
        # PARSE RECEIPT
        # -------------------------------------------------

        (

            items,

            subtotal,

            cgst,

            sgst,

            total_gst,

            grand_total

        ) = parse_receipt(
            text
        )


        # -------------------------------------------------
        # SAVE RECEIPT DATA
        # -------------------------------------------------

        session["items"] = items

        session["subtotal"] = subtotal

        session["cgst"] = cgst

        session["sgst"] = sgst

        session["total_gst"] = total_gst

        session["grand_total"] = grand_total


        # -------------------------------------------------
        # CLEAR OLD SPLIT
        # -------------------------------------------------

        session["shares"] = {}

        session["person_subtotals"] = {}

        session["person_gst"] = {}

        session["person_totals"] = {}

        session["detailed_shares"] = {}

        session["entered_quantities"] = {}


        session["error"] = ""


    except Exception as e:

        session["error"] = (

            f"OCR Error: {str(e)}"
        )


    return redirect(
        url_for("index")
    )


# =========================================================
# CALCULATE SPLIT
# =========================================================

@app.route(
    "/assign_items",
    methods=["POST"]
)
def assign_items():

    people = session.get(
        "people",
        []
    )


    items = session.get(
        "items",
        []
    )


    subtotal = session.get(
        "subtotal",
        0
    )


    total_gst = session.get(
        "total_gst",
        0
    )


    # =====================================================
    # CHECK PEOPLE
    # =====================================================

    if not people:

        session["error"] = (

            "Please add at least one person."
        )


        return redirect(
            url_for("index")
        )


    # =====================================================
    # CHECK ITEMS
    # =====================================================

    if not items:

        session["error"] = (

            "Please upload a receipt first."
        )


        return redirect(
            url_for("index")
        )


    # =====================================================
    # STORE ENTERED QUANTITIES
    # =====================================================

    entered_quantities = {}


    # =====================================================
    # VALIDATE EVERY ITEM
    # =====================================================

    for index, item in enumerate(items):

        receipt_quantity = float(

            item["quantity"]
        )


        assigned_quantity = 0.0


        person_quantities = {}


        # -------------------------------------------------
        # READ PEOPLE QUANTITIES
        # -------------------------------------------------

        for person in people:

            field_name = (

                f"item_{index}_{person}"
            )


            value = request.form.get(

                field_name,

                "0"
            ).strip()


            try:

                quantity = float(
                    value
                )


            except:

                quantity = 0.0


            # Negative quantity
            if quantity < 0:

                session["error"] = (

                    f"{item['name']}: "

                    "Quantity cannot be negative."
                )


                return redirect(
                    url_for("index")
                )


            # Individual quantity cannot exceed receipt quantity
            if quantity > receipt_quantity:

                session["error"] = (

                    f"{item['name']}: "

                    f"{person} cannot take more than "

                    f"{receipt_quantity:g} quantity."
                )


                return redirect(
                    url_for("index")
                )


            person_quantities[
                person
            ] = quantity


            entered_quantities[
                field_name
            ] = quantity


            assigned_quantity += quantity


        # -------------------------------------------------
        # QUANTITY MISMATCH
        # -------------------------------------------------

        if abs(

            assigned_quantity
            - receipt_quantity

        ) > 0.01:

            remaining = round(

                receipt_quantity
                - assigned_quantity,

                2
            )


            if remaining > 0:

                session["error"] = (

                    f"{item['name']}: "

                    f"{remaining:g} quantity still remaining. "

                    "Please assign the complete quantity."
                )


            else:

                extra = abs(
                    remaining
                )


                session["error"] = (

                    f"{item['name']}: "

                    f"{extra:g} quantity extra assigned. "

                    "Please correct the quantities."
                )


            # Preserve entered values
            session[
                "entered_quantities"
            ] = entered_quantities


            return redirect(
                url_for("index")
            )


    # =====================================================
    # CALCULATE PERSON SUBTOTALS
    # =====================================================

    person_subtotals = {

        person: 0.0

        for person in people
    }


    detailed_shares = {

        person: []

        for person in people
    }


    for index, item in enumerate(items):

        price = float(
            item["price"]
        )


        for person in people:

            field_name = (

                f"item_{index}_{person}"
            )


            quantity = entered_quantities.get(

                field_name,

                0
            )


            if quantity <= 0:

                continue


            amount = round(

                quantity * price,

                2
            )


            person_subtotals[
                person
            ] += amount


            detailed_shares[
                person
            ].append({

                "name": item["name"],

                "quantity": quantity,

                "price": price,

                "amount": amount
            })


    # =====================================================
    # ROUND SUBTOTALS
    # =====================================================

    for person in people:

        person_subtotals[
            person
        ] = round(

            person_subtotals[
                person
            ],

            2
        )


    # =====================================================
    # GST DISTRIBUTION
    # =====================================================

    person_gst = {

        person: 0.0

        for person in people
    }


    if subtotal > 0:

        for person in people:

            gst = (

                person_subtotals[
                    person
                ]

                / subtotal

            ) * total_gst


            person_gst[
                person
            ] = round(

                gst,

                2
            )


    # =====================================================
    # GST ROUNDING CORRECTION
    # =====================================================

    gst_difference = round(

        total_gst

        - sum(
            person_gst.values()
        ),

        2
    )


    if (

        people

        and abs(gst_difference) > 0

    ):

        highest_person = max(

            people,

            key=lambda person:

                person_subtotals[
                    person
                ]
        )


        person_gst[
            highest_person
        ] = round(

            person_gst[
                highest_person
            ]

            + gst_difference,

            2
        )


    # =====================================================
    # FINAL TOTAL
    # =====================================================

    person_totals = {}


    for person in people:

        person_totals[
            person
        ] = round(

            person_subtotals[
                person
            ]

            + person_gst[
                person
            ],

            2
        )


    # =====================================================
    # SAVE RESULTS
    # =====================================================

    session["person_subtotals"] = (

        person_subtotals
    )


    session["person_gst"] = (

        person_gst
    )


    session["person_totals"] = (

        person_totals
    )


    session["shares"] = (

        person_totals
    )


    session["detailed_shares"] = (

        detailed_shares
    )


    session["entered_quantities"] = (

        entered_quantities
    )


    session["error"] = ""


    return redirect(
        url_for("index")
    )


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )