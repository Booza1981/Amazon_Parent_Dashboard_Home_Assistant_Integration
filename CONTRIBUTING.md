# Contributing to Amazon Parental Dashboard Controller

Thank you for your interest in contributing! This project helps parents manage their children's screen time through Home Assistant integration.

## How to Contribute

### Reporting Bugs

If you find a bug, please open an issue with:
- A clear description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Logs from `docker-compose logs -f` (remove sensitive info)
- Your environment (OS, Docker version, Home Assistant version)

### Suggesting Features

Feature requests are welcome! Please:
- Check if the feature already exists
- Explain the use case
- Describe how it would work
- Consider if it fits the project's scope (Amazon Parental Dashboard control)

### Pull Requests

1. **Fork the repository**

2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes**
   - Follow existing code style
   - Add comments for complex logic
   - Test your changes thoroughly

4. **Test the integration**
   ```bash
   # Test locally
   python test_integration.py --broker YOUR_MQTT_IP
   
   # Test in Docker
   docker-compose build
   docker-compose up -d
   docker-compose logs -f
   ```

5. **Commit your changes**
   ```bash
   git add .
   git commit -m "Add: brief description of changes"
   ```

6. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

7. **Create a Pull Request**
   - Describe what your PR does
   - Reference any related issues
   - Include screenshots if relevant

## Development Setup

```bash
# Clone your fork
git clone https://github.com/yourusername/amazon-parental-dashboard.git
cd amazon-parental-dashboard

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Authenticate
python amazon_parental/refresh_cookies.py

# Run tests
python test_integration.py --broker YOUR_MQTT_IP
```

## Code Guidelines

- **Python Style**: Follow PEP 8
- **Comments**: Explain why, not what
- **Error Handling**: Use try/except with meaningful messages
- **Logging**: Use appropriate log levels (DEBUG, INFO, WARNING, ERROR)
- **Security**: Never commit `cookies.json` or credentials

## Testing

- Test with real Amazon account (use a test child profile if possible)
- Verify MQTT messages are published correctly
- Check Home Assistant entities appear and function
- Test Docker container startup and shutdown
- Verify cookie refresh works

## Areas for Contribution

- **Documentation improvements**
- **Bug fixes**
- **Home Assistant automation examples**
- **Better error messages**
- **Performance improvements**
- **Additional Amazon API endpoints**
- **Multi-child support enhancements**

## Questions?

Open an issue with the "question" label, or join the discussion in existing issues.

Thank you for helping make parental controls easier for everyone!

