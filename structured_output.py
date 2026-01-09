# Langchain JSON Schema
json_schema = {
  "title": "Transcript Summary",
  "description": "Provide a concise summary of the provided text.",
  "type": "object",
  "properties": {
    "sections": {
      "type": "array",
      "description": "A list of sections containing a header and two bullet points.",
      "items": {
        "type": "object",
        "properties": {
          "header": {
            "type": "string",
            "description": "A header summarizing the section."
          },
          "bullets": {
            "type": "array",
            "description": "An array of two bullet points for the section.",
            "items": {
              "type": "string",
              "description": "A bullet point."
            },
            "minItems": 2,
            "maxItems": 2
          }
        },
        "required": ["header", "bullets"]
      }
    }
  },
  "required": ["sections"]
}


# Google Gemini JSON Schema
response_schema = {
    "type": "object",
    "properties": {
        "sections": {
            "type": "array",
            "description": "A list of sections, each with a header and two bullet points.",
            "items": {
                "type": "object",
                "properties": {
                    "header": {
                        "type": "string",
                        "description": "A header for the following two bullet points."
                    },
                    "bullets": {
                        "type": "array",
                        "description": "A list of two bullet points under the header.",
                        "items": {
                            "type": "string"
                        }
                    }
                },
                "required": ["header", "bullets"]
            }
        }
    },
    "required": ["sections"]
}
