mod certora;

/// Adds two numbers together.
/// Returns the sum of x and y, wrapping on overflow (standard Rust u64 behavior).
pub fn add(x: u64, y: u64) -> u64 {
    x + y
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_add_basic() {
        assert_eq!(add(2, 3), 5);
    }

    #[test]
    fn test_add_zero() {
        assert_eq!(add(0, 0), 0);
        assert_eq!(add(42, 0), 42);
        assert_eq!(add(0, 42), 42);
    }

    #[test]
    fn test_add_large_numbers() {
        assert_eq!(add(u64::MAX - 1, 1), u64::MAX);
    }
}
