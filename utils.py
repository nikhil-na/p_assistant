from bs4 import BeautifulSoup


def clean_email(raw_list):
    # 1. Use .join() to combine the list elements into one single string
    full_text = "".join(raw_list)

    # Split into lines for easier processing
    lines = full_text.split("\n")

    headers = []
    html_body_parts = []
    is_body = False

    for line in lines:
        line = line.strip()

        # Check if we've hit the Body section
        if "Body:" in line:
            is_body = True
            # Extract everything after "Body: " on this line
            html_body_parts.append(line.split("Body:", 1)[1].strip())
            continue

        if is_body:
            html_body_parts.append(line)
        else:
            # Clean up the list bracket/quote artifact if it's at the start of the string
            if line.startswith("['"):
                line = line[2:]
            if line:
                headers.append(line)

    # 2. Use BeautifulSoup to strip HTML from the joined body text
    raw_html = "".join(html_body_parts).rstrip("']")
    soup = BeautifulSoup(raw_html, "html.parser")
    plain_body = soup.get_text().strip()

    # 3. Use .join() to assemble the final structured output
    final_output = []
    final_output.extend(headers)
    final_output.append(f"Body: {plain_body}")

    return "\n".join(final_output)