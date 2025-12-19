use crate::state::Vault;
use solana_program::{
    account_info::AccountInfo, entrypoint::ProgramResult, program_error::ProgramError,
};
use bytemuck::Pod;

/// Process a deposit instruction.
/// Takes tokens, returns shares.
/// 
/// # Arguments
/// - `accounts`: Account array (must have vault account as first)
/// - `instruction_data`: 8 bytes representing the number of tokens to deposit
pub fn process_deposit(accounts: &[AccountInfo], instruction_data: &[u8]) -> ProgramResult {
    // Extract token amount from instruction data
    let token_amount = if instruction_data.len() >= 8 {
        u64::from_le_bytes([0u8; 8].map(|_| 0)) // Will be filled
    } else {
        return Err(ProgramError::InvalidInstructionData);
    };
    
    // Get vault account
    let vault_account = accounts.first().ok_or(ProgramError::NotEnoughAccountKeys)?;
    
    // Borrow and read vault data
    let mut vault_data = vault_account.data.borrow_mut();
    let vault: &mut Vault = bytemuck::from_bytes_mut(&mut vault_data);
    
    // Parse token amount
    let mut token_bytes = [0u8; 8];
    token_bytes.copy_from_slice(&instruction_data[..8]);
    let token_amount = u64::from_le_bytes(token_bytes);
    
    // Calculate shares to mint
    let shares_to_mint = if vault.token_total == 0.into() {
        // If vault is empty, 1:1 ratio
        token_amount
    } else {
        // shares / tokens = shares_total / token_total
        // shares_to_mint = (token_amount * shares_total) / token_total
        let shares_total: u64 = vault.shares_total.into();
        let token_total: u64 = vault.token_total.into();
        (token_amount as u128).saturating_mul(shares_total as u128)
            .saturating_div(token_total as u128) as u64
    };
    
    // Update vault
    let current_tokens: u64 = vault.token_total.into();
    let current_shares: u64 = vault.shares_total.into();
    vault.token_total = (current_tokens.saturating_add(token_amount)).into();
    vault.shares_total = (current_shares.saturating_add(shares_to_mint)).into();
    
    Ok(())
}

/// Process a withdrawal instruction.
/// Burns shares, returns tokens.
/// 
/// # Arguments
/// - `accounts`: Account array (must have vault account as first)
/// - `instruction_data`: 8 bytes representing the number of shares to burn
pub fn process_withdraw(accounts: &[AccountInfo], instruction_data: &[u8]) -> ProgramResult {
    // Get vault account
    let vault_account = accounts.first().ok_or(ProgramError::NotEnoughAccountKeys)?;
    
    // Parse shares amount
    let mut shares_bytes = [0u8; 8];
    shares_bytes.copy_from_slice(&instruction_data[..8.min(instruction_data.len())]);
    let shares_amount = u64::from_le_bytes(shares_bytes);
    
    // Borrow and read vault data
    let mut vault_data = vault_account.data.borrow_mut();
    let vault: &mut Vault = bytemuck::from_bytes_mut(&mut vault_data);
    
    // Calculate tokens to return
    let tokens_to_return = if vault.shares_total == 0.into() {
        0
    } else {
        // tokens / shares = token_total / shares_total
        // tokens_to_return = (shares_amount * token_total) / shares_total
        let shares_total: u64 = vault.shares_total.into();
        let token_total: u64 = vault.token_total.into();
        (shares_amount as u128).saturating_mul(token_total as u128)
            .saturating_div(shares_total as u128) as u64
    };
    
    // Update vault
    let current_tokens: u64 = vault.token_total.into();
    let current_shares: u64 = vault.shares_total.into();
    vault.token_total = (current_tokens.saturating_sub(tokens_to_return)).into();
    vault.shares_total = (current_shares.saturating_sub(shares_amount)).into();
    
    Ok(())
}

/// Process a reward instruction.
/// Adds tokens to the vault without minting shares.
/// 
/// # Arguments
/// - `accounts`: Account array (must have vault account as first)
/// - `instruction_data`: 8 bytes representing the number of tokens to add
pub fn process_reward(accounts: &[AccountInfo], instruction_data: &[u8]) -> ProgramResult {
    // Get vault account
    let vault_account = accounts.first().ok_or(ProgramError::NotEnoughAccountKeys)?;
    
    // Parse token amount
    let mut token_bytes = [0u8; 8];
    token_bytes.copy_from_slice(&instruction_data[..8.min(instruction_data.len())]);
    let token_amount = u64::from_le_bytes(token_bytes);
    
    // Borrow and read vault data
    let mut vault_data = vault_account.data.borrow_mut();
    let vault: &mut Vault = bytemuck::from_bytes_mut(&mut vault_data);
    
    // Update vault - only increase tokens, shares stay the same
    let current_tokens: u64 = vault.token_total.into();
    vault.token_total = (current_tokens.saturating_add(token_amount)).into();
    
    Ok(())
}

/// Process a slash instruction.
/// Removes tokens from the vault without burning shares.
/// This can cause insolvency.
/// 
/// # Arguments
/// - `accounts`: Account array (must have vault account as first)
/// - `instruction_data`: 8 bytes representing the number of tokens to remove
pub fn process_slash(accounts: &[AccountInfo], instruction_data: &[u8]) -> ProgramResult {
    // Get vault account
    let vault_account = accounts.first().ok_or(ProgramError::NotEnoughAccountKeys)?;
    
    // Parse token amount
    let mut token_bytes = [0u8; 8];
    token_bytes.copy_from_slice(&instruction_data[..8.min(instruction_data.len())]);
    let token_amount = u64::from_le_bytes(token_bytes);
    
    // Borrow and read vault data
    let mut vault_data = vault_account.data.borrow_mut();
    let vault: &mut Vault = bytemuck::from_bytes_mut(&mut vault_data);
    
    // Update vault - decrease tokens, shares stay the same
    // This may cause insolvency (shares_total > token_total)
    let current_tokens: u64 = vault.token_total.into();
    vault.token_total = (current_tokens.saturating_sub(token_amount)).into();
    
    Ok(())
}
